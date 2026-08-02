"""The Telemetry Layer.

Every reading from every source converges here and follows one path:

``receive → validate → normalise → store → broadcast``

Nothing downstream may bypass it, and nothing downstream may ask where a
reading came from. That single funnel is what lets a real MIKOS sensor replace
the Digital Twin in a later phase without a line changing above this layer.
"""

from __future__ import annotations

import uuid

from sqlalchemy import bindparam, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.session import session_scope
from app.digital_twin.profiles import capabilities_for
from app.models import Asset, Telemetry
from app.schemas.enums import DataQuality, HealthState, OperationalState
from app.schemas.telemetry import TelemetryIngest
from app.services.health_engine import health_engine
from app.services.live_state import AssetIdentity, live_state
from app.utils.time import ensure_utc, utc_now
from app.websocket.manager import MessageType, connection_manager

logger = get_logger(__name__)

#: Physically implausible readings are rejected rather than stored. A negative
#: current or a 900 volt charger is a fault in the source, not a measurement,
#: and letting it through would poison every downstream average.
VALIDATION_BOUNDS: dict[str, tuple[float, float]] = {
    "voltage_v": (0.0, 1_000.0),
    "current_a": (0.0, 400.0),
    "power_w": (0.0, 250_000.0),
    "energy_kwh": (0.0, 100_000_000.0),
    "frequency_hz": (30.0, 90.0),
    "power_factor": (0.0, 1.0),
    "temperature_c": (-60.0, 250.0),
    "indoor_temperature_c": (-60.0, 90.0),
    "battery_percent": (0.0, 100.0),
    "load_percent": (0.0, 200.0),
    "runtime_hours": (0.0, 1_000_000.0),
}

#: Ticks between synchronising denormalised asset state back to the database.
ASSET_SYNC_EVERY = 10


class TelemetryService:
    """Validates, persists and publishes telemetry."""

    def __init__(self) -> None:
        self._ticks_since_sync = 0
        self._rejected = 0
        self._stored = 0

    # --- Registry ------------------------------------------------------------

    async def refresh_registry(self) -> int:
        """Reload the asset identity cache from the database."""
        async with session_scope() as session:
            identities = await self._load_identities(session)
        live_state.register_assets(identities)
        logger.info("Asset registry cached", extra={"assets": len(identities)})
        return len(identities)

    @staticmethod
    async def _load_identities(session: AsyncSession) -> list[AssetIdentity]:
        """Read assets with their scope, flattened for cheap live lookups."""
        from app.models.organization import AssetGroup, Location  # local: avoids cycle

        rows = (
            await session.execute(
                select(Asset, Location, AssetGroup)
                .outerjoin(Location, Asset.location_id == Location.id)
                .outerjoin(AssetGroup, Asset.asset_group_id == AssetGroup.id)
                .order_by(Asset.asset_code)
            )
        ).all()

        return [
            AssetIdentity(
                id=asset.id,
                asset_code=asset.asset_code,
                name=asset.name,
                asset_type=asset.asset_type,
                rated_power_w=asset.rated_power_w,
                capabilities=capabilities_for(asset.asset_type),
                organization_id=asset.organization_id,
                location_id=asset.location_id,
                location_name=location.name if location else None,
                building=location.building if location else None,
                department=location.department if location else None,
                asset_group_id=asset.asset_group_id,
                asset_group_name=group.name if group else None,
                commissioned_at=asset.commissioned_at,
            )
            for asset, location, group in rows
        ]

    # --- Validation and normalisation ----------------------------------------

    def _validate(self, reading: TelemetryIngest) -> TelemetryIngest | None:
        """Reject implausible readings; downgrade suspicious ones.

        Returns ``None`` if the reading must be discarded.
        """
        for channel, (low, high) in VALIDATION_BOUNDS.items():
            value = getattr(reading, channel, None)
            if value is None:
                continue
            if value < low or value > high:
                self._rejected += 1
                logger.warning(
                    "Telemetry rejected: value out of physical bounds",
                    extra={
                        "asset_id": str(reading.asset_id),
                        "channel": channel,
                        "value": value,
                    },
                )
                return None
        return reading

    def _normalise(self, reading: TelemetryIngest) -> TelemetryIngest:
        """Bring a reading into canonical form and derive its condition.

        Two responsibilities:

        1. Strip channels the asset category does not report, so a source that
           over-reports cannot introduce phantom data, and force every
           timestamp to UTC.
        2. Run the Health Engine. Condition is derived here, from the
           measurements, rather than accepted from the source — a sensor that
           declares its own health is asserting the conclusion the platform
           exists to reach.
        """
        identity = live_state.identity(reading.asset_id)
        updates: dict[str, object] = {"time": ensure_utc(reading.time)}

        if identity is not None:
            capabilities = identity.capabilities
            if not capabilities.energy:
                updates["energy_kwh"] = None
            if not capabilities.frequency:
                updates["frequency_hz"] = None
            if not capabilities.power_factor:
                updates["power_factor"] = None
            if not capabilities.reactive_power:
                updates["reactive_power_var"] = None
            if not capabilities.apparent_power:
                updates["apparent_power_va"] = None
            if not capabilities.relay:
                updates["relay_status"] = None
                updates["relay_operations"] = None
            if not capabilities.battery:
                updates["charging_state"] = None
                updates["battery_percent"] = None
            if not capabilities.charge_cycles:
                updates["charge_cycles"] = None
            if not capabilities.fast_charging:
                updates["fast_charging"] = None
            if not capabilities.indoor_temperature:
                updates["indoor_temperature_c"] = None

        normalised = reading.model_copy(update=updates)

        # Scored after stripping, so the engine never sees a channel the asset
        # cannot actually measure.
        assessment = health_engine.assess(normalised)
        return normalised.model_copy(
            update={"health_score": assessment.score, "health_state": assessment.state}
        )

    # --- Pipeline ------------------------------------------------------------

    async def ingest_batch(self, readings: list[TelemetryIngest]) -> int:
        """Run a batch through the full pipeline.

        This is the sink the Digital Twin Engine writes to, and the same method
        the REST ingestion endpoint and a future MQTT bridge will call.
        """
        if not readings:
            return 0

        accepted: list[TelemetryIngest] = []
        for reading in readings:
            validated = self._validate(reading)
            if validated is None:
                continue
            accepted.append(self._normalise(validated))

        if not accepted:
            return 0

        live_state.record(accepted)
        await self._persist(accepted)
        await self._broadcast(accepted)

        self._ticks_since_sync += 1
        if self._ticks_since_sync >= ASSET_SYNC_EVERY:
            self._ticks_since_sync = 0
            await self._sync_asset_state(accepted)

        self._stored += len(accepted)
        return len(accepted)

    async def _persist(self, readings: list[TelemetryIngest]) -> None:
        """Bulk-insert the batch into the hypertable.

        One multi-row statement per tick rather than one per reading: at fleet
        scale the difference between those two is the difference between a
        platform that scales and one that does not.
        """
        rows = [
            {
                "time": reading.time,
                "id": uuid.uuid4(),
                "asset_id": reading.asset_id,
                "voltage_v": reading.voltage_v,
                "current_a": reading.current_a,
                "power_w": reading.power_w,
                "reactive_power_var": reading.reactive_power_var,
                "apparent_power_va": reading.apparent_power_va,
                "energy_kwh": reading.energy_kwh,
                "frequency_hz": reading.frequency_hz,
                "power_factor": reading.power_factor,
                "temperature_c": reading.temperature_c,
                "runtime_hours": reading.runtime_hours,
                "load_percent": reading.load_percent,
                "relay_status": reading.relay_status,
                "relay_operations": reading.relay_operations,
                "charging_state": reading.charging_state,
                "battery_percent": reading.battery_percent,
                "charge_cycles": reading.charge_cycles,
                "fast_charging": reading.fast_charging,
                "indoor_temperature_c": reading.indoor_temperature_c,
                "health_score": reading.health_score,
                "health_state": reading.health_state,
                "operational_state": reading.operational_state,
                "connectivity_state": reading.connectivity_state,
                "source": reading.source,
                "quality": reading.quality,
            }
            for reading in readings
        ]

        async with session_scope() as session:
            await session.execute(insert(Telemetry), rows)

    async def _sync_asset_state(self, readings: list[TelemetryIngest]) -> None:
        """Write current condition back onto the asset rows.

        Denormalised so that fleet queries — "how many assets are critical?" —
        never touch the hypertable. Done every few ticks rather than every tick,
        because the value changes slowly and the write cost does not.
        """
        now = utc_now()
        payload = []

        for reading in readings:
            if reading.quality is DataQuality.BAD:
                # A reading the source itself distrusts must not become the
                # asset's official state.
                continue
            payload.append(
                {
                    "asset_pk": reading.asset_id,
                    "health_score": reading.health_score or 0.0,
                    "health_state": reading.health_state or HealthState.HEALTHY,
                    "operational_state": (
                        reading.operational_state or OperationalState.IDLE
                    ),
                    "connectivity_state": live_state.connectivity_for(
                        reading.asset_id, now=now
                    ),
                    "last_seen_at": reading.time,
                    # COALESCE keeps the stored value when a category does not
                    # report the channel, so a single parameter set can cover
                    # the whole heterogeneous fleet.
                    "lifetime_energy_kwh": reading.energy_kwh,
                    "relay_operations": reading.relay_operations,
                    "operating_hours": reading.runtime_hours,
                }
            )

        if not payload:
            return

        # One executemany rather than a statement per asset. At 120 devices the
        # loop this replaces issued 120 round trips every sync; batching turns
        # that into a single call whose cost barely moves as the fleet grows.
        #
        # Built against the Core table rather than the mapped class on purpose.
        # Handing a list of dicts to the ORM triggers its bulk-update-by-primary-
        # key path, which requires the primary key under its column name and
        # rejects the named bind parameters the COALESCE clauses below depend
        # on. Core gives a plain parameterised executemany.
        table = Asset.__table__
        statement = (
            update(table)
            .where(table.c.id == bindparam("asset_pk"))
            .values(
                health_score=bindparam("health_score"),
                health_state=bindparam("health_state"),
                operational_state=bindparam("operational_state"),
                connectivity_state=bindparam("connectivity_state"),
                last_seen_at=bindparam("last_seen_at"),
                # COALESCE keeps the stored value when a category does not
                # report the channel, so one parameter set covers the whole
                # heterogeneous fleet.
                lifetime_energy_kwh=func.coalesce(
                    bindparam("lifetime_energy_kwh"), table.c.lifetime_energy_kwh
                ),
                relay_operations=func.coalesce(
                    bindparam("relay_operations"), table.c.relay_operations
                ),
                operating_hours=func.coalesce(
                    bindparam("operating_hours"), table.c.operating_hours
                ),
            )
        )

        async with session_scope() as session:
            await session.execute(statement, payload)

    async def _broadcast(self, readings: list[TelemetryIngest]) -> None:
        """Publish the live tick and a sample of raw readings.

        The full batch is not sent: a browser has no use for every reading from
        every device each second. The aggregated tick drives the KPIs and
        charts, and a small slice of raw rows feeds the activity surfaces.
        """
        # Imported here rather than at module scope: the dashboard service
        # reads live state that this module populates, and importing it eagerly
        # would create a cycle at startup.
        from app.services.dashboard_service import build_live_tick

        tick = build_live_tick()
        await connection_manager.broadcast(MessageType.TICK, tick.model_dump(mode="json"))

        sample = readings[:8]
        await connection_manager.broadcast(
            MessageType.TELEMETRY,
            [reading.model_dump(mode="json") for reading in sample],
        )

    # --- Diagnostics ---------------------------------------------------------

    def status(self) -> dict[str, int]:
        return {"stored": self._stored, "rejected": self._rejected}


#: Process-wide instance. The engine, the ingestion endpoint and any future
#: bridge all publish through this one object.
telemetry_service = TelemetryService()

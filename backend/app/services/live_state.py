"""In-memory live state.

The dashboard asks "what is happening right now" several times a second across
every connected client. Answering that from the telemetry hypertable would mean
scanning time-series data on the hot path, which is the wrong tool: Timescale
is excellent at history and wasteful for a question whose answer is one row per
asset.

So the platform keeps the present in memory and the past on disk. This module
owns the present: the newest reading per asset, the asset registry, and short
rolling aggregates that back the live charts. It is rebuilt from the database
on startup and is authoritative for nothing — losing it costs a moment of
recomputation, never data.
"""

from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from app.digital_twin.profiles import capabilities_for
from app.schemas.asset import AssetCapabilities
from app.schemas.enums import (
    AssetType,
    ConnectivityState,
    HealthState,
    OperationalState,
)
from app.schemas.telemetry import TelemetryIngest
from app.utils.time import utc_now

#: Seconds without a reading after which an asset is considered offline. Set to
#: several twin intervals so ordinary jitter does not flap the state.
OFFLINE_AFTER_SECONDS = 12.0

#: One aggregate sample is retained every this many seconds.
AGGREGATE_EVERY_SECONDS = 5.0

#: Retained aggregate samples — 360 × 5s covers a 30 minute window.
AGGREGATE_HISTORY = 360

#: Points retained for the small sparkline on each asset-type card.
SPARKLINE_HISTORY = 32


@dataclass(slots=True)
class AssetIdentity:
    """Static asset facts, cached so live queries need no joins."""

    id: uuid.UUID
    asset_code: str
    name: str
    asset_type: AssetType
    rated_power_w: float
    capabilities: AssetCapabilities
    organization_id: uuid.UUID
    location_id: uuid.UUID | None = None
    location_name: str | None = None
    building: str | None = None
    department: str | None = None
    asset_group_id: uuid.UUID | None = None
    asset_group_name: str | None = None
    commissioned_at: datetime | None = None


@dataclass(slots=True)
class AggregateSample:
    """Fleet-wide averages and totals at one instant."""

    t: datetime
    voltage_v: float | None
    current_a: float | None
    power_w: float
    temperature_c: float | None
    power_factor: float | None
    energy_kwh: float
    health_score: float


@dataclass(slots=True)
class TypeRuntime:
    """Rolling figures for one asset category."""

    sparkline: deque[float] = field(
        default_factory=lambda: deque(maxlen=SPARKLINE_HISTORY)
    )
    last_sparkline_at: datetime | None = None


class LiveState:
    """Process-wide snapshot of current platform condition.

    Guarded by a lock because the Digital Twin writes from its own task while
    HTTP handlers read concurrently. The critical sections are tiny — dictionary
    assignments — so contention is negligible.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._identities: dict[uuid.UUID, AssetIdentity] = {}
        self._latest: dict[uuid.UUID, TelemetryIngest] = {}
        self._aggregates: deque[AggregateSample] = deque(maxlen=AGGREGATE_HISTORY)
        self._type_runtime: dict[AssetType, TypeRuntime] = {}
        self._last_aggregate_at: datetime | None = None
        self._organization_name: str = "INTELORA"
        self._samples_ingested: int = 0
        self._started_at: datetime = utc_now()

    # --- Registry ------------------------------------------------------------

    def set_organization(self, name: str) -> None:
        with self._lock:
            self._organization_name = name

    @property
    def organization_name(self) -> str:
        return self._organization_name

    def register_assets(self, identities: list[AssetIdentity]) -> None:
        """Replace the cached asset registry.

        Called at startup and whenever assets are created or removed, so the
        cache cannot drift from the database.
        """
        with self._lock:
            self._identities = {identity.id: identity for identity in identities}
            for identity in identities:
                self._type_runtime.setdefault(identity.asset_type, TypeRuntime())

    def identity(self, asset_id: uuid.UUID) -> AssetIdentity | None:
        return self._identities.get(asset_id)

    def identities(self) -> list[AssetIdentity]:
        with self._lock:
            return list(self._identities.values())

    def asset_types(self) -> list[AssetType]:
        with self._lock:
            return sorted({item.asset_type for item in self._identities.values()})

    @property
    def asset_count(self) -> int:
        return len(self._identities)

    # --- Ingest --------------------------------------------------------------

    def record(self, readings: list[TelemetryIngest]) -> None:
        """Absorb a batch of readings into the live snapshot."""
        if not readings:
            return
        with self._lock:
            for reading in readings:
                self._latest[reading.asset_id] = reading
            self._samples_ingested += len(readings)
            self._roll_aggregates()

    def _roll_aggregates(self) -> None:
        """Append a fleet aggregate if the sampling interval has elapsed.

        Downsampling here rather than storing every tick keeps a 30 minute
        chart window at 360 points — enough resolution to read a trend, small
        enough to serialise cheaply.
        """
        now = utc_now()
        if (
            self._last_aggregate_at is not None
            and (now - self._last_aggregate_at).total_seconds() < AGGREGATE_EVERY_SECONDS
        ):
            return
        self._last_aggregate_at = now

        readings = list(self._latest.values())
        if not readings:
            return

        def mean(values: list[float]) -> float | None:
            return sum(values) / len(values) if values else None

        voltages = [r.voltage_v for r in readings if r.voltage_v is not None]
        currents = [r.current_a for r in readings if r.current_a is not None]
        temperatures = [r.temperature_c for r in readings if r.temperature_c is not None]
        factors = [r.power_factor for r in readings if r.power_factor is not None]
        healths = [r.health_score for r in readings if r.health_score is not None]

        self._aggregates.append(
            AggregateSample(
                t=now,
                voltage_v=mean(voltages),
                current_a=mean(currents),
                power_w=sum(r.power_w or 0.0 for r in readings),
                temperature_c=mean(temperatures),
                power_factor=mean(factors),
                energy_kwh=sum(r.energy_kwh or 0.0 for r in readings),
                health_score=mean(healths) or 0.0,
            )
        )

        # Per-type sparklines track average health, which is what the asset
        # cards visualise.
        by_type: dict[AssetType, list[float]] = {}
        for reading in readings:
            identity = self._identities.get(reading.asset_id)
            if identity is None or reading.health_score is None:
                continue
            by_type.setdefault(identity.asset_type, []).append(reading.health_score)

        for asset_type, scores in by_type.items():
            runtime = self._type_runtime.setdefault(asset_type, TypeRuntime())
            runtime.sparkline.append(sum(scores) / len(scores))
            runtime.last_sparkline_at = now

    # --- Read ----------------------------------------------------------------

    def latest(self, asset_id: uuid.UUID) -> TelemetryIngest | None:
        return self._latest.get(asset_id)

    def all_latest(self) -> dict[uuid.UUID, TelemetryIngest]:
        with self._lock:
            return dict(self._latest)

    def aggregates(self) -> list[AggregateSample]:
        with self._lock:
            return list(self._aggregates)

    def sparkline(self, asset_type: AssetType) -> list[float]:
        runtime = self._type_runtime.get(asset_type)
        return list(runtime.sparkline) if runtime else []

    def connectivity_for(self, asset_id: uuid.UUID, *, now: datetime | None = None) -> ConnectivityState:
        """Infer connectivity from silence.

        A device that has stopped reporting is offline; one that has never
        reported is unknown. Neither can be asserted by a packet, which is why
        this is computed rather than stored by the source.
        """
        reading = self._latest.get(asset_id)
        if reading is None:
            return ConnectivityState.UNKNOWN
        reference = now or utc_now()
        elapsed = (reference - reading.time).total_seconds()
        return (
            ConnectivityState.OFFLINE
            if elapsed > OFFLINE_AFTER_SECONDS
            else ConnectivityState.ONLINE
        )

    def health_state_for(self, asset_id: uuid.UUID) -> HealthState:
        reading = self._latest.get(asset_id)
        if reading is None or reading.health_state is None:
            return HealthState.HEALTHY
        return reading.health_state

    def operational_state_for(self, asset_id: uuid.UUID) -> OperationalState:
        reading = self._latest.get(asset_id)
        if reading is None or reading.operational_state is None:
            return OperationalState.IDLE
        return reading.operational_state

    @property
    def samples_ingested(self) -> int:
        return self._samples_ingested

    @property
    def has_data(self) -> bool:
        return bool(self._latest)

    def capabilities(self, asset_type: AssetType) -> AssetCapabilities:
        """Capability descriptor for a category."""
        return capabilities_for(asset_type)

    def reset(self) -> None:
        """Discard live readings, keeping the registry."""
        with self._lock:
            self._latest.clear()
            self._aggregates.clear()
            self._type_runtime.clear()
            self._last_aggregate_at = None
            self._samples_ingested = 0


#: Process-wide instance.
live_state = LiveState()

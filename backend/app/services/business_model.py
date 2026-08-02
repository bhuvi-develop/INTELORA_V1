"""The Business Intelligence Layer.

Translates device condition into the unified business model every asset
exposes, whatever it reports. This is the boundary the Presentation Layer binds
to: dashboard surfaces consume :class:`AssetBusinessModel` and never touch
asset-specific telemetry shape.

Three of the model's fields — cost, efficiency and business score — do not
exist in any sensor. They are computed here, and each is defined explicitly
below rather than left as an unexplained number on an executive screen.
"""

from __future__ import annotations

import threading
import uuid
from datetime import date, datetime

from app.config import settings
from app.digital_twin.profiles import PROFILE_ORDER, get_profile
from app.schemas.asset import AssetBusinessModel, AssetTypeSummary
from app.schemas.enums import AssetType, ConnectivityState, HealthState
from app.schemas.telemetry import TelemetryIngest
from app.services.live_state import AssetIdentity, live_state
from app.utils.time import utc_now

#: Weights composing the business score. Health dominates because an unhealthy
#: asset is a liability regardless of how efficiently it happens to be running.
SCORE_WEIGHTS = {
    "health": 0.45,
    "availability": 0.25,
    "efficiency": 0.20,
    "alerts": 0.10,
}

#: Business score penalty per active alert, before the weighted blend.
ALERT_PENALTY = 22.0


class EnergyLedger:
    """Tracks per-asset energy consumed since the start of the UTC day.

    Meters report a lifetime running total, so "today's energy" is the
    difference from a baseline captured at the day's first reading. Holding the
    baseline here keeps the Cockpit's headline figure available instantly
    instead of requiring an aggregate query over the hypertable every second.

    A meter that resets — a replaced unit, or a restarted twin without
    persisted counters — would produce a negative delta; that case rebases
    rather than reporting nonsense.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._baselines: dict[uuid.UUID, tuple[date, float]] = {}

    def observe(self, asset_id: uuid.UUID, energy_kwh: float | None, moment: datetime) -> float:
        """Record a reading and return energy consumed today by this asset."""
        if energy_kwh is None:
            return 0.0

        today = moment.date()
        with self._lock:
            entry = self._baselines.get(asset_id)
            if entry is None or entry[0] != today or energy_kwh < entry[1]:
                self._baselines[asset_id] = (today, energy_kwh)
                return 0.0
            return max(0.0, energy_kwh - entry[1])

    def reset(self) -> None:
        with self._lock:
            self._baselines.clear()


energy_ledger = EnergyLedger()


def efficiency_for(reading: TelemetryIngest | None, identity: AssetIdentity) -> float:
    """Operating efficiency, 0–100.

    Composed from two signals that are available across every asset type:

    * **Electrical efficiency** — power factor where the device reports it. A
      poor power factor means apparent power the site is billed for but does
      not convert into work.
    * **Thermal headroom** — how much of the margin to the device's critical
      temperature remains. A device running hot is converting energy into heat
      instead of output.

    Assets without a power factor channel are scored on thermal headroom alone
    rather than being penalised for a measurement they cannot take.
    """
    if reading is None:
        return 0.0

    profile = get_profile(identity.asset_type)
    thermal = profile.thermal

    components: list[tuple[float, float]] = []

    if reading.power_factor is not None:
        # Map power factor onto 0–100 against the profile's own achievable
        # range, so an air conditioner is not marked down for being inductive.
        low = profile.power_factor_range[0] if profile.power_factor_range else 0.5
        span = max(1.0 - low, 0.01)
        components.append((min(100.0, max(0.0, (reading.power_factor - low) / span * 100.0)), 0.6))

    if reading.temperature_c is not None:
        span = max(thermal.critical_c - thermal.ambient_c, 1.0)
        used = (reading.temperature_c - thermal.ambient_c) / span
        components.append((min(100.0, max(0.0, (1.0 - used) * 100.0)), 0.4))

    if not components:
        return 0.0

    total_weight = sum(weight for _, weight in components)
    return sum(value * weight for value, weight in components) / total_weight


def cost_rate_for(reading: TelemetryIngest | None) -> float:
    """Operating cost run-rate, in currency units per hour.

    Derived from instantaneous power rather than metered energy so that it is
    available for every asset type, including those with no energy channel.
    Presented as a rate, never as a total, so the two are not confused.
    """
    if reading is None or reading.power_w is None:
        return 0.0
    return (reading.power_w / 1000.0) * settings.energy_tariff_per_kwh


def business_score_for(
    *,
    health_score: float,
    connectivity: ConnectivityState,
    efficiency: float,
    active_alerts: int,
) -> float:
    """Composite 0–100 view of an asset's standing.

    Blends condition, availability, efficiency and outstanding alerts. The
    intent is a single figure an executive can rank a fleet by, with the
    components remaining visible so the number is never a black box.
    """
    availability = {
        ConnectivityState.ONLINE: 100.0,
        ConnectivityState.UNKNOWN: 55.0,
        ConnectivityState.OFFLINE: 0.0,
    }[connectivity]

    alert_component = max(0.0, 100.0 - active_alerts * ALERT_PENALTY)

    score = (
        health_score * SCORE_WEIGHTS["health"]
        + availability * SCORE_WEIGHTS["availability"]
        + efficiency * SCORE_WEIGHTS["efficiency"]
        + alert_component * SCORE_WEIGHTS["alerts"]
    )
    return round(max(0.0, min(100.0, score)), 1)


def build_business_model(
    identity: AssetIdentity,
    *,
    active_alerts: int = 0,
    now: datetime | None = None,
) -> AssetBusinessModel:
    """Project one asset into the unified business contract.

    Channels the asset type does not report stay ``None``. They must render as
    "not reported", never as zero — a mobile charger contributing 0 kWh to a
    fleet average would quietly understate every energy figure on the platform.
    """
    reference = now or utc_now()
    reading = live_state.latest(identity.id)
    connectivity = live_state.connectivity_for(identity.id, now=reference)

    health_score = reading.health_score if reading and reading.health_score is not None else 0.0
    health_state = (
        reading.health_state
        if reading and reading.health_state is not None
        else HealthState.HEALTHY
    )
    operational = live_state.operational_state_for(identity.id)
    efficiency = efficiency_for(reading, identity)

    energy_today = (
        energy_ledger.observe(identity.id, reading.energy_kwh, reference) if reading else 0.0
    )

    return AssetBusinessModel(
        asset_id=identity.id,
        asset_code=identity.asset_code,
        name=identity.name,
        asset_type=identity.asset_type,
        health_score=round(health_score, 1),
        health_state=health_state,
        operational_state=operational,
        connectivity_state=connectivity,
        power_w=None if reading is None else reading.power_w,
        temperature_c=None if reading is None else reading.temperature_c,
        energy_kwh=(
            round(energy_today, 4) if identity.capabilities.energy and reading else None
        ),
        cost=round(cost_rate_for(reading), 4),
        efficiency=round(efficiency, 1),
        business_score=business_score_for(
            health_score=health_score,
            connectivity=connectivity,
            efficiency=efficiency,
            active_alerts=active_alerts,
        ),
        active_alerts=active_alerts,
        last_seen_at=None if reading is None else reading.time,
    )


def build_all_business_models(
    alert_counts: dict[uuid.UUID, int] | None = None,
    *,
    now: datetime | None = None,
) -> list[AssetBusinessModel]:
    """Project the entire fleet."""
    counts = alert_counts or {}
    reference = now or utc_now()
    return [
        build_business_model(identity, active_alerts=counts.get(identity.id, 0), now=reference)
        for identity in live_state.identities()
    ]


def summarise_asset_types(
    models: list[AssetBusinessModel],
) -> list[AssetTypeSummary]:
    """Roll the fleet up into one summary per category.

    Backs the three premium cards in Cockpit section 3. Averages are computed
    only over assets that actually report the channel, and ``capabilities``
    travels with the summary so the card can show a metric or omit it rather
    than displaying a misleading zero.
    """
    grouped: dict[AssetType, list[AssetBusinessModel]] = {}
    for model in models:
        grouped.setdefault(model.asset_type, []).append(model)

    summaries: list[AssetTypeSummary] = []

    for asset_type in PROFILE_ORDER:
        members = grouped.get(asset_type, [])
        profile = get_profile(asset_type)
        capabilities = profile.capabilities

        if not members:
            summaries.append(
                AssetTypeSummary(
                    asset_type=asset_type,
                    label=profile.label,
                    capabilities=capabilities,
                    trend=live_state.sparkline(asset_type),
                )
            )
            continue

        powers = [m.power_w for m in members if m.power_w is not None]
        temperatures = [m.temperature_c for m in members if m.temperature_c is not None]
        energies = [m.energy_kwh for m in members if m.energy_kwh is not None]

        summaries.append(
            AssetTypeSummary(
                asset_type=asset_type,
                label=profile.label,
                total=len(members),
                healthy=sum(1 for m in members if m.health_state is HealthState.HEALTHY),
                warning=sum(1 for m in members if m.health_state is HealthState.WARNING),
                critical=sum(1 for m in members if m.health_state is HealthState.CRITICAL),
                online=sum(
                    1
                    for m in members
                    if m.connectivity_state is ConnectivityState.ONLINE
                ),
                average_health=round(
                    sum(m.health_score for m in members) / len(members), 1
                ),
                total_power_w=round(sum(powers), 1) if powers else None,
                average_temperature_c=(
                    round(sum(temperatures) / len(temperatures), 1) if temperatures else None
                ),
                total_energy_kwh=(
                    round(sum(energies), 3) if capabilities.energy and energies else None
                ),
                efficiency=round(sum(m.efficiency for m in members) / len(members), 1),
                active_alerts=sum(m.active_alerts for m in members),
                capabilities=capabilities,
                trend=[round(value, 2) for value in live_state.sparkline(asset_type)],
            )
        )

    return summaries

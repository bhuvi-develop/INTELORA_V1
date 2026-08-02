"""Physical profiles for each supported asset type.

A profile is the complete description of how one category of device behaves:
what it reports, its nameplate electrical characteristics, its thermal
response, its duty cycle, which faults it can develop, and the economics the
Business Intelligence Layer needs.

Adding a new asset category means adding a profile here. Nothing in the engine,
the intelligence layers or the frontend changes — which is the scalability
requirement the SSOT places above almost everything else.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.asset import AssetCapabilities
from app.schemas.enums import AssetType, FaultType


@dataclass(frozen=True, slots=True)
class DutyCycle:
    """How a device moves between working and resting.

    ``active_fraction`` is the long-run share of time spent drawing meaningful
    power; the mean durations shape how it alternates. Modelling this properly
    is what gives the OEE layer a genuine availability figure rather than a
    constant.
    """

    active_fraction: float
    mean_active_seconds: float
    mean_idle_seconds: float
    #: Share of rated power drawn while active, as (min, max).
    active_load: tuple[float, float]
    #: Share of rated power drawn while idle (standby draw).
    idle_load: tuple[float, float]


@dataclass(frozen=True, slots=True)
class ThermalModel:
    """First-order thermal response.

    Temperature lags power rather than tracking it instantly, so overheating
    develops over tens of seconds. Without the lag, thermal faults would be
    indistinguishable from electrical noise.
    """

    ambient_c: float
    #: Steady-state rise, in kelvin, per watt dissipated.
    rise_per_watt: float
    #: Seconds to reach ~63% of a step change.
    time_constant_s: float
    #: Temperature above which the device is considered to be overheating.
    warning_c: float
    critical_c: float


@dataclass(frozen=True, slots=True)
class BatteryModel:
    """Characteristics of the battery an asset charges.

    Present only for categories that charge something. Drives a real charge
    curve — constant current while the cell fills, then a constant-voltage
    taper above the knee — rather than a random load. That distinction is what
    makes a charger's power trace look like a charger's power trace: a long
    plateau followed by a decaying tail, not noise around a mean.
    """

    #: Usable cell capacity in watt-hours. Together with charger power this
    #: sets how long a full charge realistically takes.
    capacity_wh: float
    #: State of charge above which the charger enters constant-voltage taper.
    cv_knee_percent: float
    #: Share of rated power drawn during the bulk phase.
    bulk_load: float
    #: Share of rated power drawn once full, holding the cell topped up.
    trickle_load: float
    #: Whether the category supports a boosted early-charge phase.
    supports_fast_charge: bool = False
    #: Multiplier applied to bulk load while fast charging.
    fast_charge_boost: float = 1.0
    #: State of charge at which fast charging throttles back to protect the cell.
    fast_charge_until_percent: float = 55.0
    #: Percentage points lost per hour while unplugged.
    self_discharge_per_hour: float = 4.5


@dataclass(frozen=True, slots=True)
class ThermostatModel:
    """Closed-loop temperature control, for conditioning assets.

    The compressor cycles on hysteresis around a setpoint rather than on a
    timer. This is what couples the relay to something physical: relay
    operations become a consequence of thermal load, so their count is a
    meaningful wear signal instead of an arbitrary counter.
    """

    setpoint_c: float
    #: Half-width of the deadband around the setpoint.
    hysteresis_c: float
    #: Outdoor/ambient temperature the space drifts towards when idle.
    ambient_c: float
    #: Degrees per hour the space cools while the compressor runs.
    cooling_rate_c_per_hour: float
    #: Degrees per hour the space warms towards ambient while idle.
    warming_rate_c_per_hour: float


@dataclass(frozen=True, slots=True)
class Economics:
    """Inputs the Business Intelligence Layer needs to price an asset."""

    replacement_cost: float
    maintenance_event_cost: float
    #: Hourly cost of the asset being unavailable.
    downtime_cost_per_hour: float
    #: Expected service life, used for lifecycle staging.
    design_life_hours: float


@dataclass(frozen=True, slots=True)
class TelemetryProfile:
    """Everything the twin needs to behave like one category of device."""

    asset_type: AssetType
    label: str
    capabilities: AssetCapabilities

    rated_power_w: float
    nominal_voltage_v: float
    voltage_tolerance: float
    nominal_frequency_hz: float | None
    power_factor_range: tuple[float, float] | None

    duty: DutyCycle
    thermal: ThermalModel
    economics: Economics

    fault_types: tuple[FaultType, ...]
    maintenance_task: str
    maintenance_interval_hours: float

    #: Present for categories that charge a battery.
    battery: BatteryModel | None = None
    #: Present for categories that condition a space.
    thermostat: ThermostatModel | None = None

    #: Measurement noise, as a fraction of the reading.
    noise: float = 0.012

    #: Probability per tick of a good device beginning to degrade.
    degradation_chance: float = 0.00018

    def supports(self, channel: str) -> bool:
        """Whether this asset type reports ``channel``."""
        return bool(getattr(self.capabilities, channel, False))


# --- Laptop charger ------------------------------------------------------------
# Reports the full electrical set. Bursty duty cycle: draws hard while charging,
# then falls to trickle. Fails at the adapter and through thermal stress.
LAPTOP_CHARGER = TelemetryProfile(
    asset_type=AssetType.LAPTOP_CHARGER,
    label="Laptop Chargers",
    capabilities=AssetCapabilities(
        voltage=True,
        current=True,
        power=True,
        energy=True,
        frequency=True,
        power_factor=True,
        temperature=True,
        battery=True,
        charge_cycles=True,
    ),
    rated_power_w=90.0,
    nominal_voltage_v=230.0,
    voltage_tolerance=0.045,
    nominal_frequency_hz=50.0,
    power_factor_range=(0.90, 0.98),
    duty=DutyCycle(
        active_fraction=0.58,
        mean_active_seconds=1450.0,
        mean_idle_seconds=980.0,
        active_load=(0.55, 0.97),
        idle_load=(0.015, 0.06),
    ),
    thermal=ThermalModel(
        ambient_c=24.0,
        rise_per_watt=0.28,
        time_constant_s=95.0,
        warning_c=58.0,
        critical_c=72.0,
    ),
    economics=Economics(
        replacement_cost=79.0,
        maintenance_event_cost=18.0,
        downtime_cost_per_hour=6.0,
        design_life_hours=26_000.0,
    ),
    fault_types=(
        FaultType.ADAPTER_FAILURE,
        FaultType.OVER_TEMPERATURE,
        FaultType.VOLTAGE_DROP,
        FaultType.POWER_LOSS,
        FaultType.POOR_POWER_FACTOR,
    ),
    maintenance_task="Adapter inspection and connector clean",
    maintenance_interval_hours=4_400.0,
    # A 60 Wh notebook cell on a 90 W adapter: bulk phase fills it in roughly
    # forty minutes, then the taper adds another twenty.
    battery=BatteryModel(
        capacity_wh=60.0,
        cv_knee_percent=80.0,
        bulk_load=0.88,
        trickle_load=0.04,
        self_discharge_per_hour=3.5,
    ),
)


# --- Mobile charger ------------------------------------------------------------
# Deliberately the sparse case: no frequency, no power factor, no energy meter.
# Every aggregate in the platform has to survive these absences without
# treating them as zero.
MOBILE_CHARGER = TelemetryProfile(
    asset_type=AssetType.MOBILE_CHARGER,
    label="Mobile Chargers",
    capabilities=AssetCapabilities(
        voltage=True,
        current=True,
        power=True,
        energy=False,
        frequency=False,
        power_factor=False,
        temperature=True,
        battery=True,
        charge_cycles=True,
        fast_charging=True,
    ),
    rated_power_w=33.0,
    nominal_voltage_v=230.0,
    voltage_tolerance=0.05,
    nominal_frequency_hz=None,
    power_factor_range=None,
    duty=DutyCycle(
        active_fraction=0.42,
        mean_active_seconds=760.0,
        mean_idle_seconds=1_050.0,
        active_load=(0.45, 1.0),
        idle_load=(0.01, 0.05),
    ),
    thermal=ThermalModel(
        ambient_c=24.0,
        rise_per_watt=0.62,
        time_constant_s=70.0,
        warning_c=52.0,
        critical_c=66.0,
    ),
    economics=Economics(
        replacement_cost=24.0,
        maintenance_event_cost=9.0,
        downtime_cost_per_hour=2.5,
        design_life_hours=18_000.0,
    ),
    fault_types=(
        FaultType.CABLE_FAILURE,
        FaultType.OVER_TEMPERATURE,
        FaultType.POWER_LOSS,
        FaultType.VOLTAGE_DROP,
    ),
    maintenance_task="Cable and connector replacement",
    maintenance_interval_hours=3_000.0,
    noise=0.016,
    # An 18 Wh handset cell on a 33 W supply. Fast charge drives it hard to
    # just past half, then throttles — which is exactly why a naive detector
    # reads the throttle as a power loss unless it knows the charging phase.
    battery=BatteryModel(
        capacity_wh=18.0,
        cv_knee_percent=82.0,
        bulk_load=0.72,
        trickle_load=0.05,
        supports_fast_charge=True,
        fast_charge_boost=1.34,
        fast_charge_until_percent=55.0,
        self_discharge_per_hour=6.0,
    ),
)


# --- Air conditioner -----------------------------------------------------------
# The rich case: three-way power decomposition and a switched relay whose
# operation count drives compressor wear.
AIR_CONDITIONER = TelemetryProfile(
    asset_type=AssetType.AIR_CONDITIONER,
    label="Air Conditioners",
    capabilities=AssetCapabilities(
        voltage=True,
        current=True,
        power=True,
        reactive_power=True,
        apparent_power=True,
        energy=True,
        frequency=True,
        power_factor=True,
        temperature=True,
        relay=True,
        indoor_temperature=True,
    ),
    rated_power_w=5_200.0,
    nominal_voltage_v=400.0,
    voltage_tolerance=0.035,
    nominal_frequency_hz=50.0,
    power_factor_range=(0.78, 0.95),
    duty=DutyCycle(
        active_fraction=0.66,
        mean_active_seconds=2_100.0,
        mean_idle_seconds=1_080.0,
        active_load=(0.42, 0.96),
        idle_load=(0.02, 0.05),
    ),
    thermal=ThermalModel(
        ambient_c=27.0,
        rise_per_watt=0.0042,
        time_constant_s=210.0,
        warning_c=54.0,
        critical_c=68.0,
    ),
    economics=Economics(
        replacement_cost=3_850.0,
        maintenance_event_cost=240.0,
        downtime_cost_per_hour=95.0,
        design_life_hours=52_000.0,
    ),
    fault_types=(
        FaultType.COMPRESSOR_WEAR,
        FaultType.FILTER_DIRTY,
        FaultType.OVER_CURRENT,
        FaultType.OVER_TEMPERATURE,
        FaultType.VOLTAGE_DROP,
        FaultType.POWER_LOSS,
        FaultType.RELAY_FAILURE,
        FaultType.POOR_POWER_FACTOR,
    ),
    maintenance_task="Filter clean and compressor service",
    maintenance_interval_hours=2_200.0,
    noise=0.010,
    degradation_chance=0.00026,
    # The compressor cycles on hysteresis around the setpoint, so relay
    # operations are driven by thermal load rather than a timer — which makes
    # the operation count a genuine wear signal for the APM layer.
    # Rates chosen so the compressor cycles every fifteen minutes or so, which
    # is what a correctly-sized unit actually does. Slower rates produce a
    # plausible-looking temperature trace but almost no relay transitions, and
    # the operation count is the wear signal APM depends on.
    thermostat=ThermostatModel(
        setpoint_c=23.0,
        hysteresis_c=1.1,
        ambient_c=33.0,
        cooling_rate_c_per_hour=16.0,
        warming_rate_c_per_hour=8.0,
    ),
)


PROFILES: dict[AssetType, TelemetryProfile] = {
    AssetType.LAPTOP_CHARGER: LAPTOP_CHARGER,
    AssetType.MOBILE_CHARGER: MOBILE_CHARGER,
    AssetType.AIR_CONDITIONER: AIR_CONDITIONER,
}

#: Stable display order for the three Asset Overview cards.
PROFILE_ORDER: tuple[AssetType, ...] = (
    AssetType.LAPTOP_CHARGER,
    AssetType.MOBILE_CHARGER,
    AssetType.AIR_CONDITIONER,
)


def get_profile(asset_type: AssetType) -> TelemetryProfile:
    """Return the profile for ``asset_type``.

    Raises :class:`KeyError` for an unregistered type — a loud failure at
    startup is preferable to a device that silently reports nothing.
    """
    return PROFILES[asset_type]


def capabilities_for(asset_type: AssetType) -> AssetCapabilities:
    """Capability descriptor for ``asset_type``, for the API and the UI."""
    return PROFILES[asset_type].capabilities


#: Channels that exist across every profile, used when building fleet-wide
#: aggregates that must not assume any particular asset type is present.
UNIVERSAL_CHANNELS: tuple[str, ...] = ("voltage", "current", "power", "temperature")

#: Registered fault types per asset category, exposed to the Anomaly layer.
FAULTS_BY_TYPE: dict[AssetType, tuple[FaultType, ...]] = {
    asset_type: profile.fault_types for asset_type, profile in PROFILES.items()
}

__all__ = [
    "AIR_CONDITIONER",
    "FAULTS_BY_TYPE",
    "LAPTOP_CHARGER",
    "MOBILE_CHARGER",
    "PROFILES",
    "PROFILE_ORDER",
    "UNIVERSAL_CHANNELS",
    "BatteryModel",
    "DutyCycle",
    "Economics",
    "TelemetryProfile",
    "ThermalModel",
    "ThermostatModel",
    "capabilities_for",
    "get_profile",
]

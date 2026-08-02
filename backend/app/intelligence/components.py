"""Component-level health decomposition.

A single health score tells an executive whether to worry. It tells a
technician nothing about *where* to look. This module breaks the score into the
subsystems that can actually fail and be replaced, so a prediction can say
"the thermal path is degrading" rather than "this asset is at 63".

Which components an asset has depends on its category, declared here rather
than branched on at the call site. A charger has a supply path, a conversion
stage and a thermal path; an air conditioner adds a compressor and a switching
relay. Adding a category means adding an entry, not editing the predictive
layer.

Scores are derived from the same live telemetry the Health Engine uses. Nothing
here is stored on the device or assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.digital_twin.profiles import TelemetryProfile
from app.intelligence.context import AssetWindow
from app.schemas.enums import AssetType

#: Weight of each component in the asset's overall condition. Weights sum to
#: one per category and encode consequence: a failed compressor is a failed air
#: conditioner, a marginal relay is an inconvenience.
_COMPONENT_WEIGHTS: dict[AssetType, dict[str, float]] = {
    AssetType.LAPTOP_CHARGER: {
        "supply_path": 0.25,
        "conversion_stage": 0.40,
        "thermal_path": 0.25,
        "output_cable": 0.10,
    },
    AssetType.MOBILE_CHARGER: {
        "supply_path": 0.22,
        "conversion_stage": 0.36,
        "thermal_path": 0.22,
        "output_cable": 0.20,
    },
    AssetType.AIR_CONDITIONER: {
        "supply_path": 0.18,
        "compressor": 0.34,
        "thermal_path": 0.22,
        "airflow": 0.16,
        "switching_relay": 0.10,
    },
}

#: Human-readable names, so the API never leaks an internal key.
COMPONENT_LABELS: dict[str, str] = {
    "supply_path": "Supply path",
    "conversion_stage": "Conversion stage",
    "thermal_path": "Thermal path",
    "output_cable": "Output cable",
    "compressor": "Compressor",
    "airflow": "Airflow",
    "switching_relay": "Switching relay",
}


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    """Condition of one replaceable subsystem."""

    key: str
    label: str
    #: 0–100, same scale as overall asset health.
    score: float
    #: Share of the asset's condition this component accounts for.
    weight: float
    #: What drove the score, for the technician reading it.
    basis: str

    @property
    def is_degraded(self) -> bool:
        return self.score < 78.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _supply_path(window: AssetWindow, profile: TelemetryProfile) -> tuple[float, str]:
    """Stability of the incoming supply, from voltage and frequency spread."""
    stats = window.stats.get("voltage_v")
    if stats is None or stats.samples < 10:
        return 100.0, "insufficient supply samples"

    nominal = profile.nominal_voltage_v
    if nominal <= 0:
        return 100.0, "no nominal voltage declared"

    # Two independent signals: how far the mean sits from nominal, and how much
    # it wanders. A steady 5% sag and a wildly oscillating supply are different
    # problems, and both are worse than a steady nominal.
    offset = abs(stats.mean - nominal) / nominal
    jitter = stats.stddev / nominal

    penalty = (offset / max(profile.voltage_tolerance, 0.001)) * 22.0
    penalty += (jitter / max(profile.voltage_tolerance, 0.001)) * 14.0

    frequency = window.stats.get("frequency_hz")
    if frequency is not None and profile.nominal_frequency_hz:
        drift = abs(frequency.mean - profile.nominal_frequency_hz)
        penalty += min(18.0, drift * 12.0)

    return (
        _clamp(100.0 - penalty),
        f"supply {stats.mean:.1f} V, {offset * 100:.1f}% from nominal",
    )


def _conversion_stage(window: AssetWindow, profile: TelemetryProfile) -> tuple[float, str]:
    """Efficiency of the power conversion electronics.

    Measured as delivered power against commanded load — the same
    commanded-versus-delivered comparison the rest of the platform uses,
    because a converter's job is to produce what it was asked for.
    """
    if window.mean_load_percent <= 0.5 or window.mean_running_power_w <= 0.0:
        return 100.0, "not loaded during the window"

    expected = profile.rated_power_w * (window.mean_load_percent / 100.0)
    if expected <= 1.0:
        return 100.0, "commanded load negligible"

    ratio = window.mean_running_power_w / expected
    # Shortfall is a defect; a modest overshoot is measurement spread.
    penalty = max(0.0, (1.0 - ratio)) * 120.0
    penalty += max(0.0, ratio - 1.12) * 60.0

    return (
        _clamp(100.0 - penalty),
        f"delivering {ratio * 100:.0f}% of commanded {expected:.0f} W",
    )


def _thermal_path(window: AssetWindow, profile: TelemetryProfile) -> tuple[float, str]:
    """Ability to shed heat, from the temperature distribution."""
    stats = window.stats.get("temperature_c")
    if stats is None or stats.samples < 10:
        return 100.0, "insufficient thermal samples"

    thermal = profile.thermal
    headroom = max(thermal.critical_c - thermal.ambient_c, 1.0)
    # Judged on the peak rather than the mean: thermal damage is done at the
    # top of the cycle, and an asset that averages comfortably while spiking
    # past its limit is not healthy.
    used = (stats.maximum - thermal.ambient_c) / headroom

    return (
        _clamp(100.0 - max(0.0, used - 0.55) * 150.0),
        f"peak {stats.maximum:.1f} °C against {thermal.critical_c:.0f} °C limit",
    )


def _output_cable(window: AssetWindow, profile: TelemetryProfile) -> tuple[float, str]:
    """Integrity of the output connection, from current stability.

    A failing cable shows as erratic current *that the load does not explain* —
    the contact making and breaking rather than the battery filling.

    That qualifier is the whole measurement. Raw current variation is useless
    here: a charger's current is supposed to swing from a few milliamps at idle
    to full bulk charge and back, so its coefficient of variation is large and
    perfectly healthy. Scoring on it marks every working charger as a failing
    cable.

    Since P = V·I·cosφ, current and power move together when the connection is
    sound. Comparing their coefficients of variation cancels the duty cycle out
    and leaves only the part of the current's behaviour that power cannot
    account for.
    """
    current = window.stats.get("current_a")
    power = window.stats.get("power_w")

    if current is None or current.samples < 20 or current.mean <= 0.0001:
        return 100.0, "insufficient current samples"

    current_cv = current.stddev / current.mean

    if power is None or power.mean <= 0.0001:
        # No power reference to normalise against; report neutral rather than
        # guess from raw variation.
        return 100.0, "no power reference for comparison"

    power_cv = power.stddev / power.mean

    # Current should be no less steady than the power it delivers. A modest
    # allowance absorbs measurement noise and voltage ripple.
    excess = max(0.0, current_cv - power_cv - 0.12)

    return (
        _clamp(100.0 - excess * 140.0),
        f"current varies {current_cv * 100:.0f}% against {power_cv * 100:.0f}% for power",
    )


def _compressor(window: AssetWindow, profile: TelemetryProfile) -> tuple[float, str]:
    """Compressor condition, from current draw and power factor together.

    A worn compressor pulls more current for the same work and its power factor
    falls. Either alone is ambiguous; together they are characteristic.
    """
    current = window.stats.get("current_a")
    factor = window.stats.get("power_factor")

    if current is None or current.samples < 20:
        return 100.0, "insufficient compressor samples"

    penalty = 0.0
    basis: list[str] = []

    if profile.nominal_voltage_v > 0:
        rated_current = profile.rated_power_w / profile.nominal_voltage_v
        if rated_current > 0:
            ratio = current.mean / rated_current
            penalty += max(0.0, ratio - 0.85) * 70.0
            basis.append(f"draw {ratio * 100:.0f}% of rated")

    if factor is not None and profile.power_factor_range is not None:
        floor = profile.power_factor_range[0]
        penalty += max(0.0, floor - factor.mean) * 220.0
        basis.append(f"power factor {factor.mean:.2f}")

    return _clamp(100.0 - penalty), ", ".join(basis) or "nominal"


def _airflow(window: AssetWindow, profile: TelemetryProfile) -> tuple[float, str]:
    """Airflow restriction, inferred from thermal behaviour under load.

    A choked filter shows as elevated temperature *and* elevated current at
    normal commanded load — the unit works harder against the restriction.
    """
    temperature = window.stats.get("temperature_c")
    if temperature is None or temperature.samples < 20:
        return 100.0, "insufficient samples"

    thermal = profile.thermal
    rise = temperature.mean - thermal.ambient_c
    expected_rise = (thermal.warning_c - thermal.ambient_c) * 0.55
    excess = max(0.0, rise - expected_rise) / max(expected_rise, 1.0)

    return (
        _clamp(100.0 - excess * 55.0),
        f"mean rise {rise:.1f} K above ambient",
    )


def _switching_relay(window: AssetWindow, _: TelemetryProfile) -> tuple[float, str]:
    """Relay wear, from accumulated operations.

    Contactors are rated in operations, not hours, which is exactly why the
    thermostat model drives the relay from thermal load rather than a timer.
    """
    reading = window.latest
    operations = reading.relay_operations if reading else None
    if operations is None:
        return 100.0, "no relay operations reported"

    # A commercial contactor is typically rated around a million operations.
    consumed = operations / 1_000_000.0
    return _clamp(100.0 - consumed * 100.0), f"{operations:,} operations"


_CALCULATORS = {
    "supply_path": _supply_path,
    "conversion_stage": _conversion_stage,
    "thermal_path": _thermal_path,
    "output_cable": _output_cable,
    "compressor": _compressor,
    "airflow": _airflow,
    "switching_relay": _switching_relay,
}


def assess_components(
    window: AssetWindow, profile: TelemetryProfile
) -> list[ComponentHealth]:
    """Score every component this asset category has."""
    weights = _COMPONENT_WEIGHTS.get(profile.asset_type, {})
    results: list[ComponentHealth] = []

    for key, weight in weights.items():
        calculator = _CALCULATORS.get(key)
        if calculator is None:
            continue
        score, basis = calculator(window, profile)
        results.append(
            ComponentHealth(
                key=key,
                label=COMPONENT_LABELS.get(key, key.replace("_", " ").title()),
                score=round(score, 1),
                weight=weight,
                basis=basis,
            )
        )

    return results


def weakest_component(components: list[ComponentHealth]) -> ComponentHealth | None:
    """The component most responsible for the asset's condition.

    Weighted, not raw: a lightly-weighted subsystem at 60 matters less than the
    dominant one at 75, and the prediction should point at whichever will
    actually take the asset down.
    """
    if not components:
        return None
    return min(components, key=lambda item: item.score + (1.0 - item.weight) * 25.0)


__all__ = [
    "COMPONENT_LABELS",
    "ComponentHealth",
    "assess_components",
    "weakest_component",
]

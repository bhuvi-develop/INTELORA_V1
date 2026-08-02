"""Root cause diagnosis and anomaly-level recommendations.

A fault type records *what* the platform observed. This module works out *why*,
and what to do about it.

The distinction matters more than it first appears. Two air conditioners can
both report over-temperature: one because its filter is choked, another because
the supply is sagging and it is drawing compensating current to hold output.
Same symptom, unrelated remedies. A platform that reports only the symptom
leaves the diagnosis to whoever reads the alert, which is exactly the work it
exists to do for them.

Diagnosis is contextual, not a lookup. The same fault resolves to different
causes depending on what else is happening on the asset at that moment — which
is why this takes the whole reading and the analysis window, not just the fault
code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.digital_twin.profiles import TelemetryProfile
from app.intelligence.context import AssetWindow
from app.schemas.enums import AssetType, FaultType, RootCause
from app.schemas.telemetry import TelemetryIngest


@dataclass(frozen=True, slots=True)
class Diagnosis:
    """A cause and the action it implies."""

    root_cause: RootCause
    #: One sentence a technician can act on, naming the evidence.
    explanation: str
    #: The concrete next step.
    recommendation: str


#: Fallback cause per fault, used when no contextual rule fires. Every fault
#: resolves to something — "undetermined" is a diagnosis of last resort, not a
#: default anyone should see routinely.
_DEFAULT_CAUSE: dict[FaultType, RootCause] = {
    FaultType.VOLTAGE_SPIKE: RootCause.SUPPLY_INSTABILITY,
    FaultType.VOLTAGE_DROP: RootCause.SUPPLY_INSTABILITY,
    FaultType.OVER_CURRENT: RootCause.LOAD_MISMATCH,
    FaultType.UNDER_CURRENT: RootCause.CONNECTION_INTEGRITY,
    FaultType.POWER_SPIKE: RootCause.LOAD_MISMATCH,
    FaultType.POWER_LOSS: RootCause.CONNECTION_INTEGRITY,
    FaultType.OVER_TEMPERATURE: RootCause.THERMAL_DISSIPATION,
    FaultType.FREQUENCY_VARIATION: RootCause.SUPPLY_INSTABILITY,
    FaultType.POOR_POWER_FACTOR: RootCause.REACTIVE_LOADING,
    FaultType.ABNORMAL_ENERGY: RootCause.METERING_FAULT,
    FaultType.DEVICE_OFFLINE: RootCause.POWER_INTERRUPTION,
    FaultType.COMMUNICATION_FAILURE: RootCause.NETWORK_PATH,
    FaultType.UNEXPECTED_BEHAVIOUR: RootCause.UNDETERMINED,
    FaultType.ADAPTER_FAILURE: RootCause.COMPONENT_DEGRADATION,
    FaultType.CABLE_FAILURE: RootCause.CONNECTION_INTEGRITY,
    FaultType.COMPRESSOR_WEAR: RootCause.MECHANICAL_WEAR,
    FaultType.FILTER_DIRTY: RootCause.AIRFLOW_RESTRICTION,
    FaultType.RELAY_FAILURE: RootCause.MECHANICAL_WEAR,
}

#: What to do about each cause. Phrased as an instruction, not an observation.
_ACTION: dict[RootCause, str] = {
    RootCause.SUPPLY_INSTABILITY: (
        "Check the upstream supply and distribution board feeding this circuit. "
        "If neighbouring assets show the same pattern, the fault is on the feed, "
        "not the device."
    ),
    RootCause.THERMAL_DISSIPATION: (
        "Verify ventilation clearance and ambient conditions around the unit. "
        "Reduce sustained load until case temperature returns inside its envelope."
    ),
    RootCause.AIRFLOW_RESTRICTION: (
        "Clean or replace the air filter and confirm the coil is clear. Restricted "
        "airflow raises current draw and shortens compressor life."
    ),
    RootCause.COMPONENT_DEGRADATION: (
        "Schedule component-level inspection. The device is delivering less than "
        "commanded and the shortfall is widening."
    ),
    RootCause.CONNECTION_INTEGRITY: (
        "Inspect the cable, connector and termination. Intermittent contact "
        "presents as current collapse without any supply fault."
    ),
    RootCause.LOAD_MISMATCH: (
        "Review what is connected. Draw is above the nameplate envelope for the "
        "commanded load, which stresses the supply path."
    ),
    RootCause.REACTIVE_LOADING: (
        "Investigate reactive loading on this circuit. Apparent power is being "
        "billed without producing useful work; correction may be economic."
    ),
    RootCause.MECHANICAL_WEAR: (
        "Schedule mechanical service. Wear signatures are present in the current "
        "and power-factor traces."
    ),
    RootCause.NETWORK_PATH: (
        "Check the gateway and network path to this asset. Telemetry is arriving "
        "irregularly while the device appears powered."
    ),
    RootCause.POWER_INTERRUPTION: (
        "Confirm the asset is powered and physically connected. It has stopped "
        "reporting entirely."
    ),
    RootCause.METERING_FAULT: (
        "Validate the energy meter against measured power. The accumulated total "
        "is inconsistent with observed draw."
    ),
    RootCause.UNDETERMINED: (
        "Inspect the asset. Individual channels are within range but their "
        "relationship is not physically consistent."
    ),
}


def _thermal_context(
    reading: TelemetryIngest, window: AssetWindow, profile: TelemetryProfile
) -> RootCause:
    """Distinguish the several reasons an asset runs hot.

    Overheating is a symptom with at least three distinct causes, and they call
    for entirely different work.
    """
    # Drawing well above expectation while hot: the heat is a consequence of
    # excess current, not of poor cooling.
    if (
        reading.current_a is not None
        and profile.nominal_voltage_v > 0
        and reading.current_a
        > (profile.rated_power_w / profile.nominal_voltage_v) * 1.15
    ):
        return (
            RootCause.AIRFLOW_RESTRICTION
            if profile.asset_type is AssetType.AIR_CONDITIONER
            else RootCause.LOAD_MISMATCH
        )

    # Hot while barely loaded points at the cooling path itself.
    if reading.load_percent is not None and reading.load_percent < 45.0:
        return RootCause.THERMAL_DISSIPATION

    # A steadily worsening thermal trend on a mature asset reads as wear.
    if window.health_slope_per_hour < -1.5:
        return RootCause.COMPONENT_DEGRADATION

    return RootCause.THERMAL_DISSIPATION


def _power_loss_context(
    reading: TelemetryIngest, window: AssetWindow
) -> RootCause:
    """Separate a supply problem from a device problem."""
    # Voltage is fine but current has collapsed: the fault is in the device or
    # its connection, not the feed.
    if reading.voltage_v is not None and reading.current_a is not None:
        voltage_stats = window.stats.get("voltage_v")
        supply_steady = (
            voltage_stats is None
            or abs(voltage_stats.z_score(reading.voltage_v)) < 2.0
        )
        if supply_steady:
            return RootCause.CONNECTION_INTEGRITY

    return RootCause.SUPPLY_INSTABILITY


def diagnose(
    *,
    fault_type: FaultType,
    reading: TelemetryIngest | None,
    window: AssetWindow,
    profile: TelemetryProfile,
    evidence: str,
) -> Diagnosis:
    """Determine cause and remedy for one detected fault.

    ``evidence`` is the detector's own description of what it saw; it is folded
    into the explanation so the diagnosis always cites the measurement that
    produced it rather than asserting a conclusion on its own authority.
    """
    cause = _DEFAULT_CAUSE.get(fault_type, RootCause.UNDETERMINED)

    # Contextual refinement, where the same symptom has several origins.
    if reading is not None:
        if fault_type is FaultType.OVER_TEMPERATURE:
            cause = _thermal_context(reading, window, profile)
        elif fault_type is FaultType.POWER_LOSS:
            cause = _power_loss_context(reading, window)
        elif fault_type is FaultType.UNDER_CURRENT and profile.battery is not None:
            # On a charger, a current collapse is far more often the cable than
            # the supply.
            cause = RootCause.CONNECTION_INTEGRITY
        elif (
            fault_type is FaultType.OVER_CURRENT
            and profile.asset_type is AssetType.AIR_CONDITIONER
        ):
            # A compressor pulling hard is usually working against restricted
            # airflow before it is genuinely worn.
            cause = (
                RootCause.AIRFLOW_RESTRICTION
                if window.health_slope_per_hour > -2.0
                else RootCause.MECHANICAL_WEAR
            )

    explanation = f"{evidence} Diagnosed as {cause.value.replace('_', ' ')}."

    return Diagnosis(
        root_cause=cause,
        explanation=explanation,
        recommendation=_ACTION.get(cause, _ACTION[RootCause.UNDETERMINED]),
    )


__all__ = ["Diagnosis", "diagnose"]

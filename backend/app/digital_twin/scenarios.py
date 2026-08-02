"""Scenario state machine for virtual devices.

A scenario is *engine-side behaviour*, not an asset status. The platform never
sees "failure" or "recovery" as a state — it sees a device whose readings drift
out of band and whose health score falls into ``critical``, then climbs back.
Keeping the distinction here is what stops simulation vocabulary leaking into
the domain model.

Each scenario contributes multiplicative or additive distortions to otherwise
healthy readings, so the same physics runs underneath every scenario and only
the deviations differ.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.digital_twin.profiles import TelemetryProfile
from app.schemas.enums import FaultType, TwinScenario


@dataclass(frozen=True, slots=True)
class Distortion:
    """Multiplicative and additive deviations applied to a healthy reading.

    Values are neutral by default, so a scenario only states what it changes.
    """

    voltage_scale: float = 1.0
    current_scale: float = 1.0
    power_scale: float = 1.0
    power_factor_delta: float = 0.0
    frequency_delta: float = 0.0
    temperature_delta: float = 0.0
    #: Extra thermal rise per watt, used by faults that impede cooling.
    thermal_penalty: float = 0.0
    #: Direct subtraction from the health score, before clamping.
    health_penalty: float = 0.0
    #: Whether the device reports at all this tick.
    reporting: bool = True

    def blend(self, other: Distortion, weight: float) -> Distortion:
        """Interpolate towards ``other`` by ``weight`` in ``[0, 1]``.

        Used to ramp a fault in gradually rather than switching it on between
        one second and the next, which would be trivially detectable and
        unrealistic.
        """
        w = max(0.0, min(1.0, weight))

        def lerp(a: float, b: float) -> float:
            return a + (b - a) * w

        return Distortion(
            voltage_scale=lerp(self.voltage_scale, other.voltage_scale),
            current_scale=lerp(self.current_scale, other.current_scale),
            power_scale=lerp(self.power_scale, other.power_scale),
            power_factor_delta=lerp(self.power_factor_delta, other.power_factor_delta),
            frequency_delta=lerp(self.frequency_delta, other.frequency_delta),
            temperature_delta=lerp(self.temperature_delta, other.temperature_delta),
            thermal_penalty=lerp(self.thermal_penalty, other.thermal_penalty),
            health_penalty=lerp(self.health_penalty, other.health_penalty),
            reporting=other.reporting if w > 0.5 else self.reporting,
        )


NEUTRAL = Distortion()

#: The characteristic signature of each fault, at full severity.
FAULT_SIGNATURES: dict[FaultType, Distortion] = {
    FaultType.ADAPTER_FAILURE: Distortion(
        voltage_scale=0.88, power_scale=0.72, power_factor_delta=-0.14,
        temperature_delta=9.0, health_penalty=42.0,
    ),
    FaultType.CABLE_FAILURE: Distortion(
        current_scale=0.63, power_scale=0.60, voltage_scale=0.94,
        temperature_delta=6.0, health_penalty=38.0,
    ),
    FaultType.COMPRESSOR_WEAR: Distortion(
        current_scale=1.26, power_scale=1.19, power_factor_delta=-0.11,
        temperature_delta=7.5, thermal_penalty=0.0016, health_penalty=34.0,
    ),
    FaultType.FILTER_DIRTY: Distortion(
        current_scale=1.13, power_scale=1.11, temperature_delta=6.5,
        thermal_penalty=0.0022, health_penalty=22.0,
    ),
    FaultType.OVER_TEMPERATURE: Distortion(
        temperature_delta=17.0, thermal_penalty=0.0031, power_factor_delta=-0.05,
        health_penalty=36.0,
    ),
    FaultType.OVER_CURRENT: Distortion(
        current_scale=1.42, power_scale=1.28, temperature_delta=8.0, health_penalty=40.0,
    ),
    FaultType.VOLTAGE_DROP: Distortion(
        voltage_scale=0.84, current_scale=1.15, power_scale=0.93, health_penalty=30.0,
    ),
    FaultType.POWER_LOSS: Distortion(
        power_scale=0.34, current_scale=0.38, health_penalty=46.0,
    ),
    FaultType.POOR_POWER_FACTOR: Distortion(
        power_factor_delta=-0.21, current_scale=1.12, health_penalty=18.0,
    ),
    FaultType.RELAY_FAILURE: Distortion(
        current_scale=0.55, power_scale=0.52, health_penalty=44.0,
    ),
    FaultType.FREQUENCY_VARIATION: Distortion(
        frequency_delta=-1.1, health_penalty=20.0,
    ),
    FaultType.VOLTAGE_SPIKE: Distortion(
        voltage_scale=1.16, temperature_delta=4.0, health_penalty=26.0,
    ),
    FaultType.DEVICE_OFFLINE: Distortion(reporting=False, health_penalty=50.0),
}


@dataclass(slots=True)
class ScenarioState:
    """The scenario a device is currently in, and how far through it is."""

    scenario: TwinScenario = TwinScenario.HEALTHY
    fault_type: FaultType | None = None
    #: Ticks remaining in the current scenario.
    remaining: int = 0
    #: Total ticks the current scenario was scheduled for.
    duration: int = 1
    #: How pronounced the fault is, in ``[0, 1]``.
    intensity: float = 0.0

    @property
    def progress(self) -> float:
        """Fraction of the scenario elapsed, in ``[0, 1]``."""
        if self.duration <= 0:
            return 1.0
        return 1.0 - (self.remaining / self.duration)


class ScenarioController:
    """Drives one virtual device through its behavioural lifecycle.

    The natural progression is healthy → degrading → failure → recovery →
    healthy. Maintenance and offline are interruptions that can occur from the
    healthy state. Durations are randomised per device so that a fleet started
    at the same instant does not fail in lockstep.
    """

    #: Scenario durations in ticks, as (minimum, maximum).
    DURATIONS: dict[TwinScenario, tuple[int, int]] = {
        TwinScenario.HEALTHY: (900, 3_600),
        TwinScenario.DEGRADING: (240, 620),
        TwinScenario.FAILURE: (90, 260),
        TwinScenario.RECOVERY: (120, 300),
        TwinScenario.MAINTENANCE: (180, 480),
        TwinScenario.OFFLINE: (30, 150),
    }

    def __init__(self, profile: TelemetryProfile, rng: random.Random) -> None:
        self._profile = profile
        self._rng = rng
        self.state = ScenarioState(
            scenario=TwinScenario.HEALTHY,
            remaining=self._duration(TwinScenario.HEALTHY),
            duration=self._duration(TwinScenario.HEALTHY),
        )

    def _duration(self, scenario: TwinScenario) -> int:
        low, high = self.DURATIONS[scenario]
        return self._rng.randint(low, high)

    def _enter(self, scenario: TwinScenario, fault_type: FaultType | None = None) -> None:
        duration = self._duration(scenario)
        self.state = ScenarioState(
            scenario=scenario,
            fault_type=fault_type,
            remaining=duration,
            duration=duration,
            intensity=0.0,
        )

    def force(self, scenario: TwinScenario, fault_type: FaultType | None = None) -> None:
        """Externally drive the device into a scenario.

        Exposed so that the twin control API can demonstrate a specific
        condition on request.
        """
        if fault_type is None and scenario in {TwinScenario.DEGRADING, TwinScenario.FAILURE}:
            fault_type = self._rng.choice(self._profile.fault_types)
        self._enter(scenario, fault_type)

    def reset(self) -> None:
        """Return the device to healthy operation."""
        self._enter(TwinScenario.HEALTHY)

    def advance(self) -> ScenarioState:
        """Move one tick forward and return the resulting state."""
        state = self.state
        state.remaining -= 1

        # Intensity ramps in over the first half of a fault scenario and eases
        # back out during recovery, so transitions are gradual.
        if state.scenario in {TwinScenario.DEGRADING, TwinScenario.FAILURE}:
            state.intensity = min(1.0, state.progress * 2.0)
        elif state.scenario is TwinScenario.RECOVERY:
            state.intensity = max(0.0, 1.0 - state.progress)
        else:
            state.intensity = 0.0

        if state.remaining > 0:
            return state

        self._transition()
        return self.state

    def _transition(self) -> None:
        """Choose the next scenario when the current one expires."""
        current = self.state.scenario
        fault = self.state.fault_type

        if current is TwinScenario.HEALTHY:
            roll = self._rng.random()
            if roll < 0.55:
                self._enter(
                    TwinScenario.DEGRADING, self._rng.choice(self._profile.fault_types)
                )
            elif roll < 0.80:
                self._enter(TwinScenario.MAINTENANCE)
            elif roll < 0.90:
                self._enter(TwinScenario.OFFLINE)
            else:
                self._enter(TwinScenario.HEALTHY)
            return

        if current is TwinScenario.DEGRADING:
            # Most degradation is caught and serviced; some runs to failure.
            if self._rng.random() < 0.45:
                self._enter(TwinScenario.FAILURE, fault)
            else:
                self._enter(TwinScenario.RECOVERY, fault)
            return

        if current is TwinScenario.FAILURE:
            self._enter(TwinScenario.RECOVERY, fault)
            return

        # Recovery, maintenance and offline all return to healthy operation.
        self._enter(TwinScenario.HEALTHY)

    def distortion(self) -> Distortion:
        """The deviation to apply to this tick's healthy readings."""
        state = self.state

        if state.scenario is TwinScenario.OFFLINE:
            return FAULT_SIGNATURES[FaultType.DEVICE_OFFLINE]

        if state.scenario is TwinScenario.MAINTENANCE:
            # Powered down for service: no load, no thermal rise, health intact.
            return Distortion(
                current_scale=0.0, power_scale=0.0, temperature_delta=-4.0, health_penalty=0.0
            )

        if state.fault_type is None or state.intensity <= 0.0:
            return NEUTRAL

        signature = FAULT_SIGNATURES.get(state.fault_type, NEUTRAL)

        # Degradation reaches only part of the way to a full fault signature;
        # failure reaches all of it.
        ceiling = 0.55 if state.scenario is TwinScenario.DEGRADING else 1.0
        return NEUTRAL.blend(signature, state.intensity * ceiling)

    def describe(self) -> str:
        """Short human-readable label, for the twin status endpoint."""
        state = self.state
        if state.fault_type is None:
            return state.scenario.value
        return f"{state.scenario.value}:{state.fault_type.value}"


__all__ = [
    "FAULT_SIGNATURES",
    "NEUTRAL",
    "Distortion",
    "ScenarioController",
    "ScenarioState",
]

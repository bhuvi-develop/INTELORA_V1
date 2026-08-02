"""The Health Engine.

Derives an asset's condition from its electrical telemetry, every reading,
without the data source having any say in the matter.

That independence is the point. A physical charger reports volts, amps, watts
and degrees; it has no opinion about whether it is healthy. If a source could
declare its own health, the platform would be displaying the source's
conclusion rather than reaching one, and every intelligence layer above would
inherit that assertion instead of the evidence. So health is computed here, in
the Telemetry Layer, and the twin emits nothing but measurements.

Scoring is a weighted penalty model over six channels, each judged against the
asset category's own envelope rather than a global constant. A charger running
at 55 °C is in trouble; an air-conditioning compressor at 55 °C is working
normally. Penalties are subtractive and bounded so no single channel can drive
the score to zero on its own, and the result is smoothed across readings —
condition is a physical property and does not jump forty points in a second.

The three health states are thresholds on the resulting number. They are never
assigned directly anywhere in the platform.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from app.digital_twin.profiles import TelemetryProfile, get_profile
from app.schemas.enums import ChargingState, HealthState
from app.schemas.telemetry import TelemetryIngest
from app.services.live_state import live_state

#: Score boundaries. Health is a number; the states are derived from it.
HEALTH_WARNING_BELOW = 78.0
HEALTH_CRITICAL_BELOW = 52.0

#: Smoothing factor applied to each new score. Low enough that a single noisy
#: reading cannot move the needle, high enough that a genuine fault registers
#: within a few seconds rather than a few minutes.
SMOOTHING = 0.09

#: Maximum penalty each channel may contribute, in points. The weights encode
#: consequence: sustained overheating destroys a device, a drifting power
#: factor merely costs money.
PENALTY_CEILING = {
    "temperature": 34.0,
    "voltage": 26.0,
    "current": 24.0,
    "power": 18.0,
    "power_factor": 12.0,
    "frequency": 10.0,
}


def health_state_for(score: float) -> HealthState:
    """Derive the health dimension from the numeric score.

    The single place in the platform where a health state is produced.
    """
    if score < HEALTH_CRITICAL_BELOW:
        return HealthState.CRITICAL
    if score < HEALTH_WARNING_BELOW:
        return HealthState.WARNING
    return HealthState.HEALTHY


@dataclass(slots=True)
class HealthAssessment:
    """A scored reading, with the reasoning that produced it."""

    score: float
    state: HealthState
    #: Points deducted per channel, so the score can always be explained.
    penalties: dict[str, float]

    @property
    def dominant_channel(self) -> str | None:
        """The channel contributing most of the deduction, if any."""
        if not self.penalties:
            return None
        channel, penalty = max(self.penalties.items(), key=lambda item: item[1])
        return channel if penalty > 0.5 else None


def _graded(value: float, soft: float, hard: float, ceiling: float) -> float:
    """Two-segment penalty ramp.

    Nothing below ``soft``; a gentle slope from there to ``hard`` worth a third
    of the ceiling; then a steep slope beyond.

    The gentle segment is what makes the score a *score*. A model that stays at
    100 until a hard limit trips produces a fleet where every asset reads
    exactly 100 and nothing can be ranked, compared or watched trending in the
    wrong direction — which is most of what an asset health index is for. The
    early slope means a device drifting towards its limit is visibly worse than
    one sitting comfortably inside it, well before anybody needs paging.
    """
    if value <= soft:
        return 0.0

    if value <= hard:
        span = max(hard - soft, 0.001)
        return ((value - soft) / span) * ceiling * 0.33

    span = max(hard - soft, 0.001)
    over = (value - hard) / span
    return min(ceiling, ceiling * 0.33 + over * ceiling * 0.67)


def _thermal_penalty(reading: TelemetryIngest, profile: TelemetryProfile) -> float:
    """Penalty for thermal stress, graded from well before the warning line.

    The soft threshold sits partway between ambient and the warning limit, so a
    device running hot registers as degraded long before it becomes an
    incident. Thermal stress is cumulative damage, not a step change at an
    arbitrary temperature.
    """
    if reading.temperature_c is None:
        return 0.0

    thermal = profile.thermal
    soft = thermal.ambient_c + (thermal.warning_c - thermal.ambient_c) * 0.62

    return _graded(
        reading.temperature_c,
        soft=soft,
        hard=thermal.warning_c,
        ceiling=PENALTY_CEILING["temperature"],
    )


def _voltage_penalty(reading: TelemetryIngest, profile: TelemetryProfile) -> float:
    """Penalty for supply voltage outside tolerance, in either direction."""
    if reading.voltage_v is None:
        return 0.0

    nominal = profile.nominal_voltage_v
    if nominal <= 0:
        return 0.0

    deviation = abs(reading.voltage_v - nominal) / nominal
    tolerance = profile.voltage_tolerance

    # Graded from two-thirds of tolerance, so supply drifting towards the edge
    # of its band is visible before it leaves it.
    return _graded(
        deviation,
        soft=tolerance * 0.66,
        hard=tolerance,
        ceiling=PENALTY_CEILING["voltage"],
    )


def _current_penalty(reading: TelemetryIngest, profile: TelemetryProfile) -> float:
    """Penalty for drawing above the nameplate current."""
    if reading.current_a is None or profile.nominal_voltage_v <= 0:
        return 0.0

    rated_current = profile.rated_power_w / profile.nominal_voltage_v
    if rated_current <= 0:
        return 0.0

    return _graded(
        reading.current_a,
        soft=rated_current * 1.02,
        hard=rated_current * 1.18,
        ceiling=PENALTY_CEILING["current"],
    )


def _power_penalty(reading: TelemetryIngest, profile: TelemetryProfile) -> float:
    """Penalty for delivering less power than the operating mode implies.

    Only meaningful while the asset should be working hard. A charger tapering
    towards full, or one sitting idle, is *supposed* to draw almost nothing —
    scoring that as a fault would mark every device on the platform unhealthy
    the moment it finished its job. This is precisely why the charging phase
    travels with the reading.
    """
    if reading.power_w is None or reading.load_percent is None:
        return 0.0

    # Tapering, trickling, complete or idle: low draw is correct behaviour.
    if reading.charging_state in {
        ChargingState.IDLE,
        ChargingState.TOPPING_OFF,
        ChargingState.TRICKLE,
        ChargingState.COMPLETE,
    }:
        return 0.0

    # Only judge assets that are commanded to a substantial load.
    if reading.load_percent < 35.0:
        return 0.0

    expected = profile.rated_power_w * (reading.load_percent / 100.0)
    if expected <= 1.0 or reading.power_w >= expected * 0.7:
        return 0.0

    shortfall = (expected * 0.7 - reading.power_w) / (expected * 0.7)
    return min(PENALTY_CEILING["power"], shortfall * PENALTY_CEILING["power"])


def _power_factor_penalty(
    reading: TelemetryIngest, profile: TelemetryProfile
) -> float:
    """Penalty for apparent power that is not converted into work."""
    if reading.power_factor is None or profile.power_factor_range is None:
        return 0.0

    floor = profile.power_factor_range[0]

    # Inverted: lower is worse, so the ramp runs on the shortfall.
    return _graded(
        floor - reading.power_factor,
        soft=0.0,
        hard=floor * 0.12,
        ceiling=PENALTY_CEILING["power_factor"],
    )


def _frequency_penalty(reading: TelemetryIngest, profile: TelemetryProfile) -> float:
    """Penalty for supply frequency drift."""
    if reading.frequency_hz is None or profile.nominal_frequency_hz is None:
        return 0.0

    drift = abs(reading.frequency_hz - profile.nominal_frequency_hz)

    return _graded(
        drift, soft=0.25, hard=0.8, ceiling=PENALTY_CEILING["frequency"]
    )


class HealthEngine:
    """Scores every reading and smooths the result per asset.

    Holds one previous score per asset so condition evolves rather than
    flickering. The state is a cache, not a record — losing it costs a few
    seconds of re-convergence and nothing else.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._scores: dict[uuid.UUID, float] = {}

    def assess(self, reading: TelemetryIngest) -> HealthAssessment:
        """Score one reading against its category's envelope."""
        identity = live_state.identity(reading.asset_id)
        if identity is None:
            # Unknown asset: report neutral rather than inventing a verdict.
            return HealthAssessment(score=100.0, state=HealthState.HEALTHY, penalties={})

        profile = get_profile(identity.asset_type)

        penalties = {
            "temperature": _thermal_penalty(reading, profile),
            "voltage": _voltage_penalty(reading, profile),
            "current": _current_penalty(reading, profile),
            "power": _power_penalty(reading, profile),
            "power_factor": _power_factor_penalty(reading, profile),
            "frequency": _frequency_penalty(reading, profile),
        }

        raw = 100.0 - sum(penalties.values())
        raw = max(0.0, min(100.0, raw))

        with self._lock:
            previous = self._scores.get(reading.asset_id)
            # First sighting adopts the raw score outright; there is nothing to
            # smooth against, and easing up from a default would misreport a
            # device that was already faulty when the platform first saw it.
            smoothed = raw if previous is None else previous + (raw - previous) * SMOOTHING
            smoothed = max(0.0, min(100.0, smoothed))
            self._scores[reading.asset_id] = smoothed

        return HealthAssessment(
            score=round(smoothed, 2),
            state=health_state_for(smoothed),
            penalties={key: round(value, 2) for key, value in penalties.items() if value > 0},
        )

    def current(self, asset_id: uuid.UUID) -> float | None:
        """Last smoothed score for an asset, if one has been computed."""
        return self._scores.get(asset_id)

    def forget(self, asset_id: uuid.UUID) -> None:
        """Drop an asset's history, so it re-converges from its next reading."""
        with self._lock:
            self._scores.pop(asset_id, None)

    def reset(self) -> None:
        """Clear every score. Used when the fleet is rebuilt."""
        with self._lock:
            self._scores.clear()

    @property
    def tracked_assets(self) -> int:
        return len(self._scores)


#: Process-wide instance. The Telemetry Layer scores every reading through it.
health_engine = HealthEngine()

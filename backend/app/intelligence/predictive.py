"""Layer 2 — Predictive Maintenance.

Projects the observed health trend forward to estimate when an asset will
degrade past the point of reliable operation.

The method is deliberately transparent: extrapolate the health slope measured
over the analysis window to the critical threshold. It is a linear model and
makes no claim otherwise — every result carries the confidence that goes with
it, and confidence rises with sample count and falls when the trend is noisy.
A later phase replaces the estimator; nothing above this layer changes when it
does, because the output contract stays the same.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.digital_twin.profiles import get_profile
from app.intelligence.components import assess_components, weakest_component
from app.intelligence.context import AssetWindow, IntelligenceContext
from app.services.health_engine import HEALTH_CRITICAL_BELOW
from app.models import PredictiveResult
from app.schemas.enums import FaultType, RiskLevel

#: A slope shallower than this is treated as stable rather than degrading.
#:
#: Calibration matters more here than anywhere else in the platform. Health is
#: already smoothed on ingest, so genuine degradation produces slopes of tens
#: of points per hour while ordinary jitter produces fractions of a point. A
#: threshold set near the noise floor extrapolates that jitter into imminent
#: failure dates and flags a healthy fleet as critical — an internally
#: contradictory output that destroys confidence in every other figure shown.
SIGNIFICANT_SLOPE = 2.5

#: Cap on remaining useful life. Beyond this the estimate is meaningless and
#: reporting "fails in nine years" would imply precision that does not exist.
MAX_RUL_HOURS = 8_760.0

#: Minimum window samples before a prediction is published at all. At 1 Hz this
#: is roughly two minutes of history.
MIN_SAMPLES = 120

#: Minimum elapsed window, in hours, before a slope is trusted. Two samples
#: milliseconds apart can imply any gradient at all.
MIN_WINDOW_HOURS = 0.08

#: Horizon over which a projected failure counts as urgent. Beyond a week out,
#: a forecast is a planning input rather than an operational one.
URGENCY_HORIZON_HOURS = 168.0


def _risk_for(probability: float, rul_hours: float | None) -> RiskLevel:
    """Combine failure likelihood with urgency.

    A high probability far in the future is a planning item; a high probability
    within a shift is an operational one. Urgency escalates risk, but it never
    sets it alone — a short projected life derived from a weak signal is a
    statement about the model's confidence, not about the asset, and treating
    it as severe is how an entire healthy fleet ends up flagged red.
    """
    if rul_hours is not None:
        if rul_hours <= 24.0 and probability >= 0.50:
            return RiskLevel.SEVERE
        if rul_hours <= 96.0 and probability >= 0.35:
            return RiskLevel.HIGH

    if probability >= 0.70:
        return RiskLevel.SEVERE
    if probability >= 0.45:
        return RiskLevel.HIGH
    if probability >= 0.20:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _failure_probability(window: AssetWindow, rul_hours: float | None) -> float:
    """Blend current condition, degradation speed and open faults.

    Three independent signals, because any one alone is misleading: a healthy
    asset degrading fast matters, and so does a chronically unhealthy asset
    that is currently stable.
    """
    health = window.health_last if window.health_last is not None else 100.0

    # Condition: how far below the critical threshold the asset already sits.
    condition = max(0.0, (100.0 - health) / 100.0)

    # Urgency: how soon the trend reaches critical.
    #
    # Squared over a one-week horizon rather than linear over a fortnight.
    # A linear curve treats "fails in five days" as nearly as pressing as
    # "fails within the hour", which floods the risk register and leaves an
    # operator no way to tell what actually needs attention today. The squared
    # form keeps urgency low until failure is genuinely close.
    urgency = 0.0
    if rul_hours is not None:
        urgency = max(0.0, min(1.0, 1.0 - (rul_hours / URGENCY_HORIZON_HOURS))) ** 2

    # Fault burden: open alerts, saturating so one asset cannot dominate.
    burden = min(1.0, window.open_alerts * 0.18 + window.critical_alerts * 0.25)

    probability = condition * 0.45 + urgency * 0.35 + burden * 0.20
    return round(max(0.0, min(0.99, probability)), 4)


def _confidence(window: AssetWindow, slope: float) -> float:
    """How much weight the estimate deserves.

    Rises with the number of samples behind it and with the clarity of the
    trend; a barely-perceptible slope produces a low-confidence projection even
    when the arithmetic is well determined.
    """
    sample_confidence = min(0.85, 0.40 + window.sample_count / 2_400.0)
    trend_clarity = min(1.0, abs(slope) / 4.0)
    return round(min(0.97, sample_confidence * (0.65 + 0.35 * trend_clarity)), 4)


def _dominant_fault(window: AssetWindow) -> FaultType | None:
    """The fault most likely to end this asset's life, if any is open."""
    if not window.open_fault_keys:
        return None
    for key in window.open_fault_keys:
        try:
            return FaultType(key)
        except ValueError:
            continue
    return None


async def run(session: AsyncSession, context: IntelligenceContext) -> int:
    """Produce a prediction for every asset with enough history."""
    written = 0

    for window in context.assets():
        # Publishing a forecast from a handful of samples spanning seconds is
        # worse than publishing none: it looks authoritative and is not.
        if (
            window.sample_count < MIN_SAMPLES
            or window.window_hours < MIN_WINDOW_HOURS
            or window.health_last is None
        ):
            continue

        slope = window.health_slope_per_hour
        health = window.health_last

        rul_hours: float | None = None
        predicted_at = None

        if slope < -SIGNIFICANT_SLOPE:
            headroom = max(0.0, health - HEALTH_CRITICAL_BELOW)
            rul_hours = min(MAX_RUL_HOURS, headroom / abs(slope))
            predicted_at = context.computed_at + timedelta(hours=rul_hours)
        elif health < HEALTH_CRITICAL_BELOW:
            # Already past the threshold: failure is present, not forecast.
            rul_hours = 0.0
            predicted_at = context.computed_at

        probability = _failure_probability(window, rul_hours)
        risk = _risk_for(probability, rul_hours)
        confidence = _confidence(window, slope)

        if rul_hours is None:
            rationale = (
                f"Health is stable at {health:.0f} with no significant downward trend "
                f"over the last {context.window_minutes} minutes."
            )
        elif rul_hours <= 0.0:
            rationale = (
                f"Health has already fallen to {health:.0f}, below the critical "
                f"threshold of {HEALTH_CRITICAL_BELOW:.0f}."
            )
        else:
            rationale = (
                f"Health is falling at {abs(slope):.2f} points per hour from "
                f"{health:.0f}; at that rate it reaches the critical threshold in "
                f"{rul_hours:.0f} hours."
            )

        # Component decomposition. A score says whether to worry; this says
        # which subsystem to look at, and it comes from the same live telemetry
        # rather than from any stored assumption about the device.
        profile = get_profile(window.identity.asset_type)
        components = assess_components(window, profile)
        weakest = weakest_component(components)

        if weakest is not None and weakest.is_degraded:
            rationale += (
                f" The {weakest.label.lower()} is the weakest subsystem at "
                f"{weakest.score:.0f} ({weakest.basis})."
            )

        session.add(
            PredictiveResult(
                asset_id=window.identity.id,
                computed_at=context.computed_at,
                failure_probability=probability,
                remaining_useful_life_hours=(
                    None if rul_hours is None else round(rul_hours, 2)
                ),
                predicted_failure_at=predicted_at,
                confidence=confidence,
                risk_level=risk,
                degradation_rate_per_hour=round(slope, 4),
                dominant_fault_type=_dominant_fault(window),
                rationale=rationale,
                component_health=[
                    {
                        "key": component.key,
                        "label": component.label,
                        "score": component.score,
                        "weight": component.weight,
                        "basis": component.basis,
                        "degraded": component.is_degraded,
                    }
                    for component in components
                ],
                weakest_component=weakest.key if weakest else None,
                weakest_component_score=weakest.score if weakest else None,
            )
        )
        written += 1

    return written

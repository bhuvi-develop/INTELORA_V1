"""Layer 4 — Prescriptive Optimisation.

Turns diagnosis into a decision: given what is wrong and what is coming, what
should actually be done, and what is it worth?

Every output is **advisory**. INTELORA observes and recommends; it issues no
commands, and nothing in this layer reaches a device. That boundary is
deliberate and must survive future phases.

This layer is the source of the Cockpit's *today's cost saving* figure. That
number is an estimate of avoided cost — the downtime and replacement expense a
recommended action is expected to prevent, discounted by the confidence that
the underlying prediction is right. Presenting undiscounted savings would
overstate the platform's certainty.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.digital_twin.profiles import get_profile
from app.intelligence.context import IntelligenceContext
from app.models import PredictiveResult, PrescriptiveResult, PreventiveResult
from app.schemas.enums import (
    BusinessImpact,
    FaultType,
    RecommendedAction,
    RiskLevel,
)

#: Expected hours of downtime avoided by acting on each recommendation.
DOWNTIME_AVOIDED_HOURS: dict[RecommendedAction, float] = {
    RecommendedAction.CONTINUE_MONITORING: 0.0,
    RecommendedAction.REDUCE_LOAD: 1.5,
    RecommendedAction.INCREASE_SETPOINT: 1.0,
    RecommendedAction.SCHEDULE_INSPECTION: 4.0,
    RecommendedAction.CLEAN_FILTER: 6.0,
    RecommendedAction.REPLACE_COMPONENT: 12.0,
    RecommendedAction.REPLACE_ASSET: 24.0,
}

#: Fraction of consumption a recommendation is expected to remove.
ENERGY_REDUCTION: dict[RecommendedAction, float] = {
    RecommendedAction.CONTINUE_MONITORING: 0.0,
    RecommendedAction.REDUCE_LOAD: 0.12,
    RecommendedAction.INCREASE_SETPOINT: 0.09,
    RecommendedAction.SCHEDULE_INSPECTION: 0.02,
    RecommendedAction.CLEAN_FILTER: 0.11,
    RecommendedAction.REPLACE_COMPONENT: 0.07,
    RecommendedAction.REPLACE_ASSET: 0.18,
}


#: Share of an asset's *available* health headroom each action is expected to
#: recover. Expressed as a fraction rather than absolute points, because a
#: filter clean on a badly-choked unit returns far more than the same clean on
#: one that is nearly fine.
HEALTH_RECOVERY: dict[RecommendedAction, float] = {
    RecommendedAction.CONTINUE_MONITORING: 0.0,
    RecommendedAction.REDUCE_LOAD: 0.35,
    RecommendedAction.INCREASE_SETPOINT: 0.28,
    RecommendedAction.SCHEDULE_INSPECTION: 0.30,
    RecommendedAction.CLEAN_FILTER: 0.62,
    RecommendedAction.REPLACE_COMPONENT: 0.80,
    RecommendedAction.REPLACE_ASSET: 1.0,
}


def _business_impact(
    *,
    cost_saving: float,
    risk: RiskLevel,
    failure_probability: float,
    action: RecommendedAction,
) -> BusinessImpact:
    """Rank how much acting on this recommendation is worth.

    Deliberately not a pure function of money. A cheap action that averts an
    imminent failure outranks an expensive one that shaves a little energy off
    a healthy asset, and a ranking that ignores that sends people to the wrong
    work first.
    """
    if action is RecommendedAction.CONTINUE_MONITORING:
        return BusinessImpact.NEGLIGIBLE

    if risk is RiskLevel.SEVERE and failure_probability >= 0.6:
        return BusinessImpact.CRITICAL

    if cost_saving >= 500.0 or (risk is RiskLevel.HIGH and failure_probability >= 0.4):
        return BusinessImpact.HIGH

    if cost_saving >= 80.0 or risk in {RiskLevel.HIGH, RiskLevel.MODERATE}:
        return BusinessImpact.MODERATE

    return BusinessImpact.LOW


def _impact_statement(
    *,
    action: RecommendedAction,
    impact: BusinessImpact,
    cost_saving: float,
    health_gain: float,
    asset_code: str,
) -> str:
    """State plainly what happens if nothing is done."""
    if action is RecommendedAction.CONTINUE_MONITORING:
        return (
            f"{asset_code} is operating within expectations. No intervention is "
            "justified at present."
        )

    consequence = {
        BusinessImpact.CRITICAL: (
            "Failure is likely and imminent; unplanned downtime should be "
            "expected if this is deferred."
        ),
        BusinessImpact.HIGH: (
            "Deferring this raises the probability of an unplanned outage "
            "materially."
        ),
        BusinessImpact.MODERATE: (
            "Deferring this allows a known degradation to continue."
        ),
        BusinessImpact.LOW: "Deferring this carries limited near-term risk.",
        BusinessImpact.NEGLIGIBLE: "No material consequence to deferring.",
    }[impact]

    return (
        f"{consequence} Acting is estimated to avoid {cost_saving:,.2f} in cost "
        f"and recover about {health_gain:.0f} health points on {asset_code}."
    )


def _choose_action(
    *,
    fault: FaultType | None,
    risk: RiskLevel,
    maintenance_due: bool,
    failure_probability: float,
) -> tuple[RecommendedAction, str]:
    """Select the action, and say plainly why.

    Fault-specific remedies come first because they are the cheapest effective
    intervention; escalation to replacement is reserved for assets whose
    predicted failure is both likely and imminent.
    """
    if risk is RiskLevel.SEVERE and failure_probability >= 0.75:
        return (
            RecommendedAction.REPLACE_ASSET,
            "Failure is both likely and imminent. Replacement is expected to cost "
            "less than the unplanned outage it prevents.",
        )

    if fault is FaultType.FILTER_DIRTY:
        return (
            RecommendedAction.CLEAN_FILTER,
            "Restricted airflow is forcing higher current draw. Cleaning the filter "
            "restores efficiency and removes the thermal load driving degradation.",
        )

    if fault is FaultType.COMPRESSOR_WEAR:
        return (
            RecommendedAction.REPLACE_COMPONENT,
            "Compressor wear is raising current draw and depressing power factor. "
            "Component replacement halts the degradation before it reaches failure.",
        )

    if fault is FaultType.OVER_TEMPERATURE:
        return (
            RecommendedAction.REDUCE_LOAD,
            "The asset is running above its thermal envelope. Reducing load lowers "
            "dissipation and slows heat-driven ageing.",
        )

    if fault in {FaultType.ADAPTER_FAILURE, FaultType.CABLE_FAILURE}:
        return (
            RecommendedAction.REPLACE_COMPONENT,
            "The supply path is degrading. Replacing the affected component "
            "restores delivery before the asset drops out of service.",
        )

    if fault is FaultType.OVER_CURRENT:
        return (
            RecommendedAction.REDUCE_LOAD,
            "Current draw is above the rated envelope. Reducing load protects the "
            "asset while the root cause is investigated.",
        )

    if fault is FaultType.POOR_POWER_FACTOR:
        return (
            RecommendedAction.SCHEDULE_INSPECTION,
            "Power factor has fallen below the expected floor, meaning apparent "
            "power is being billed without producing work. Inspection is warranted.",
        )

    if maintenance_due or risk in {RiskLevel.HIGH, RiskLevel.SEVERE}:
        return (
            RecommendedAction.SCHEDULE_INSPECTION,
            "Condition and service interval both indicate attention is due. "
            "Scheduling now avoids an unplanned intervention later.",
        )

    return (
        RecommendedAction.CONTINUE_MONITORING,
        "The asset is operating within expected parameters. No action is required "
        "beyond continued observation.",
    )


async def run(session: AsyncSession, context: IntelligenceContext) -> int:
    """Produce a recommendation for every asset assessed this cycle."""
    predictions = {
        row.asset_id: row
        for row in (
            await session.scalars(
                select(PredictiveResult).where(
                    PredictiveResult.computed_at == context.computed_at
                )
            )
        ).all()
    }
    preventive = {
        row.asset_id: row
        for row in (
            await session.scalars(
                select(PreventiveResult).where(
                    PreventiveResult.computed_at == context.computed_at
                )
            )
        ).all()
    }

    written = 0

    for window in context.assets():
        prediction = predictions.get(window.identity.id)
        if prediction is None:
            continue

        plan = preventive.get(window.identity.id)
        profile = get_profile(window.identity.asset_type)

        action, advice = _choose_action(
            fault=prediction.dominant_fault_type,
            risk=prediction.risk_level,
            maintenance_due=bool(plan and plan.maintenance_due),
            failure_probability=prediction.failure_probability,
        )

        # Energy saving: a day of the asset's typical running consumption,
        # multiplied by the reduction the action is expected to deliver.
        daily_kwh = (window.mean_running_power_w / 1000.0) * 24.0 * max(
            window.running_ratio, 0.05
        )
        energy_saving = daily_kwh * ENERGY_REDUCTION[action]

        # Cost saving: avoided downtime plus, where replacement is advised, the
        # residual value of catching it before a hard failure. Discounted by
        # prediction confidence so the figure never overstates certainty.
        downtime_saving = (
            DOWNTIME_AVOIDED_HOURS[action]
            * profile.economics.downtime_cost_per_hour
            * prediction.failure_probability
        )
        if action is RecommendedAction.REPLACE_ASSET:
            downtime_saving += profile.economics.replacement_cost * 0.15

        cost_saving = (downtime_saving + energy_saving * 0.14) * prediction.confidence

        # --- Expected health improvement --------------------------------------
        # How much condition the asset should recover if the action is taken.
        # Bounded by the headroom actually available: an asset at 95 cannot
        # gain twenty points, and promising that it will is how a platform
        # loses credibility the first time someone checks.
        current_health = window.health_last if window.health_last is not None else 100.0
        headroom = max(0.0, 100.0 - current_health)
        health_gain = min(headroom, headroom * HEALTH_RECOVERY[action])

        # --- Business impact ----------------------------------------------------
        # Money alone does not rank a recommendation. Avoiding ten dollars on an
        # asset about to fail outranks saving fifty on one that is fine, so
        # impact blends the saving with the consequence of inaction.
        impact = _business_impact(
            cost_saving=cost_saving,
            risk=prediction.risk_level,
            failure_probability=prediction.failure_probability,
            action=action,
        )

        target_component = prediction.weakest_component
        impact_statement = _impact_statement(
            action=action,
            impact=impact,
            cost_saving=cost_saving,
            health_gain=health_gain,
            asset_code=window.identity.asset_code,
        )

        session.add(
            PrescriptiveResult(
                asset_id=window.identity.id,
                computed_at=context.computed_at,
                recommended_action=action,
                advice=advice,
                priority=prediction.risk_level,
                energy_saving_kwh=round(max(0.0, energy_saving), 4),
                cost_saving=round(max(0.0, cost_saving), 2),
                confidence=prediction.confidence,
                business_impact=impact,
                expected_health_gain=round(health_gain, 2),
                target_component=target_component,
                impact_statement=impact_statement,
            )
        )
        written += 1

    return written

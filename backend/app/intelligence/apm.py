"""Layer 5 — Asset Performance Management.

Consumes every layer beneath it and produces the fleet's reliability and
business position. The outputs divide into two families, which the UI keeps
visually separate per product principle 4:

* **Reliability engineering** — health index, MTBF, MTTR, availability,
  reliability, maintainability, criticality, lifecycle stage.
* **Business** — cost exposure, maintenance cost, ROI, risk score, business
  value, repair-versus-replace, and the resulting fleet ranking.

Standard reliability definitions are used throughout rather than invented ones,
so the figures mean what a maintenance engineer expects them to mean.
"""

from __future__ import annotations

import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.digital_twin.profiles import get_profile
from app.intelligence.context import AssetWindow, IntelligenceContext
from app.models import ApmResult, Asset, PredictiveResult, PreventiveResult
from app.schemas.enums import (
    BusinessImpact,
    ConnectivityState,
    LifecycleStage,
    RiskLevel,
)
from app.services.live_state import live_state
from app.utils.time import hours_between

#: Assumed hours to restore an asset when no repair history exists yet.
DEFAULT_MTTR_HOURS = 4.0

#: Repair time above which maintainability is considered poor.
MAINTAINABILITY_CEILING_HOURS = 24.0

#: Weighting between remaining calendar life and present condition when scoring
#: lifecycle. Condition carries less than age because a temporary dip in health
#: should not read as permanent consumption of service life.
LIFECYCLE_AGE_WEIGHT = 0.7
LIFECYCLE_HEALTH_WEIGHT = 0.3

#: Exposure bands, in currency units, used with criticality to grade business
#: impact. Expressed against the most expensive asset the platform models — a
#: 5.2 kW air conditioner — so the scale stays meaningful as the fleet grows
#: rather than being tuned to a particular fleet size.
IMPACT_EXPOSURE_REFERENCE = 5_000.0


def _lifecycle_stage(age_hours: float, design_life_hours: float, health: float) -> LifecycleStage:
    """Where the asset sits in its service life.

    Age alone is not enough: a young asset in poor health has effectively aged
    faster than the calendar suggests, so condition pulls the stage forward.
    """
    consumed = age_hours / design_life_hours if design_life_hours > 0 else 0.0

    if consumed < 0.05:
        return LifecycleStage.COMMISSIONING
    if consumed >= 0.85 or health < 40.0:
        return LifecycleStage.END_OF_LIFE
    if consumed >= 0.55 or health < 65.0:
        return LifecycleStage.WEAR
    return LifecycleStage.NORMAL


def _criticality(*, rated_power_w: float, risk_score: float) -> RiskLevel:
    """How much the business depends on this asset staying up.

    Combines physical significance — a 5 kW chiller matters more than a 33 W
    charger — with the risk it is currently carrying.
    """
    scale = min(1.0, rated_power_w / 5_000.0)
    combined = scale * 0.45 + risk_score * 0.55

    if combined >= 0.72:
        return RiskLevel.SEVERE
    if combined >= 0.48:
        return RiskLevel.HIGH
    if combined >= 0.25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _lifecycle_score(
    age_hours: float, design_life_hours: float, health: float
) -> float:
    """How much service life remains, as a 0–100 score.

    The stage above answers "which band is this asset in"; this answers "how
    far through is it". Both are needed: a fleet where forty assets sit in
    ``wear`` is unrankable on stage alone, and stage is what a manager filters
    on while score is what orders the result.
    """
    if design_life_hours <= 0:
        return 100.0

    remaining = max(0.0, 1.0 - (age_hours / design_life_hours))
    blended = (
        remaining * 100.0 * LIFECYCLE_AGE_WEIGHT + health * LIFECYCLE_HEALTH_WEIGHT
    )
    return round(max(0.0, min(100.0, blended)), 2)


def _utilization(window: AssetWindow) -> float:
    """Share of the window the asset was actually doing work.

    Deliberately not availability. An asset can be perfectly available and
    barely used — that is an over-provisioning finding, not a reliability one,
    and collapsing the two into one number hides it completely.
    """
    return round(max(0.0, min(1.0, window.running_ratio)), 4)


def _energy_cost(window: AssetWindow) -> float:
    """Cost of the energy this asset consumed across the window.

    Prefers the metered counter, which is authoritative where a category has
    one. Mobile chargers do not meter energy, so the figure falls back to
    integrating measured power over the running portion of the window — the
    same physical quantity obtained from a channel every category does report.
    That keeps the KPI populated fleet-wide without inventing a reading, which
    the two-model rule requires: the *telemetry* differs, the *business* value
    does not.

    A negative delta means the counter reset or rolled; energy consumed can
    only climb, so the integral is used instead of a nonsense negative cost.
    """
    kwh = window.energy_delta_kwh

    if kwh is None or kwh < 0.0:
        running_hours = window.window_hours * window.running_ratio
        kwh = (window.mean_running_power_w * running_hours) / 1000.0

    return round(max(0.0, kwh) * settings.energy_tariff_per_kwh, 4)


def _business_impact(cost_exposure: float, criticality: RiskLevel) -> BusinessImpact:
    """How much the business should care about this asset.

    Money alone is not impact: a large exposure on a non-critical asset is a
    budgeting item, while a moderate exposure on a severe-criticality one is an
    operational problem. Sharing the scale with the prescriptive layer means an
    APM finding and a recommendation about the same asset rank together instead
    of contradicting each other.
    """
    weight = {
        RiskLevel.SEVERE: 1.0,
        RiskLevel.HIGH: 0.75,
        RiskLevel.MODERATE: 0.5,
        RiskLevel.LOW: 0.25,
    }[criticality]

    exposure = min(1.0, cost_exposure / IMPACT_EXPOSURE_REFERENCE)
    combined = exposure * 0.6 + weight * 0.4

    if combined >= 0.75:
        return BusinessImpact.CRITICAL
    if combined >= 0.55:
        return BusinessImpact.HIGH
    if combined >= 0.32:
        return BusinessImpact.MODERATE
    if combined >= 0.12:
        return BusinessImpact.LOW
    return BusinessImpact.NEGLIGIBLE


def _mtbf(operating_hours: float, failures: int) -> float | None:
    """Mean time between failures.

    Undefined with no failures on record — reporting infinity would be
    technically true and practically useless, so the field stays empty until
    there is history to compute from.
    """
    if failures <= 0:
        return None
    return round(operating_hours / failures, 2)


def _reliability(operating_hours: float, mtbf_hours: float | None) -> float:
    """Probability of surviving the next 24 hours.

    The exponential reliability function, R(t) = e^(−t/MTBF), evaluated at one
    day. With no failure history, reliability is assumed high but not certain.
    """
    if mtbf_hours is None or mtbf_hours <= 0:
        return 0.95 if operating_hours > 0 else 1.0
    return round(math.exp(-24.0 / mtbf_hours), 4)


def _availability(window: AssetWindow, connectivity: ConnectivityState) -> float:
    """Share of the window the asset was both reachable and usable.

    An unreachable asset is unavailable regardless of what its last reading
    said, which is why connectivity gates the figure.
    """
    if connectivity is ConnectivityState.OFFLINE:
        return 0.0
    if window.sample_count == 0:
        return 0.0

    expected = (window.window_hours * 3600.0) / 1.0 if window.window_hours else 0.0
    reported = min(1.0, window.sample_count / expected) if expected > 0 else 1.0

    # Time in maintenance is planned downtime and still counts against
    # availability, which is what makes the OEE figure above it honest.
    usable = window.running_ratio + max(0.0, 1.0 - window.running_ratio) * 0.85
    return round(max(0.0, min(1.0, reported * usable)), 4)


async def run(session: AsyncSession, context: IntelligenceContext) -> int:
    """Compute APM results for the fleet and rank them."""
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
    plans = {
        row.asset_id: row
        for row in (
            await session.scalars(
                select(PreventiveResult).where(
                    PreventiveResult.computed_at == context.computed_at
                )
            )
        ).all()
    }
    assets = {
        asset.id: asset
        for asset in (
            await session.scalars(
                select(Asset).where(Asset.id.in_(list(context.windows.keys())))
            )
        ).all()
    }

    # Baseline for the trend deltas: the computation immediately before this
    # one. Reading it here, once, is what lets every asset report a direction
    # of travel without the read path having to reconstruct one later from
    # whatever history happens to have survived retention.
    previous: dict[uuid.UUID, ApmResult] = {}
    previous_at = await session.scalar(
        select(func.max(ApmResult.computed_at)).where(
            ApmResult.computed_at < context.computed_at
        )
    )
    if previous_at is not None:
        previous = {
            row.asset_id: row
            for row in (
                await session.scalars(
                    select(ApmResult).where(ApmResult.computed_at == previous_at)
                )
            ).all()
        }

    results: list[ApmResult] = []

    for window in context.assets():
        asset = assets.get(window.identity.id)
        if asset is None:
            continue

        profile = get_profile(window.identity.asset_type)
        economics = profile.economics

        health = window.health_last if window.health_last is not None else asset.health_score
        connectivity = live_state.connectivity_for(window.identity.id, now=context.computed_at)
        prediction = predictions.get(window.identity.id)
        plan = plans.get(window.identity.id)

        failure_probability = prediction.failure_probability if prediction else 0.0

        # --- Reliability engineering -----------------------------------------
        operating_hours = max(asset.operating_hours, 1.0)
        mtbf = _mtbf(operating_hours, window.lifetime_failures)
        mttr = window.mean_repair_hours or (
            DEFAULT_MTTR_HOURS if window.lifetime_failures else None
        )
        availability = _availability(window, connectivity)
        reliability = _reliability(operating_hours, mtbf)
        maintainability = round(
            max(
                0.0,
                min(
                    1.0,
                    1.0 - ((mttr or DEFAULT_MTTR_HOURS) / MAINTAINABILITY_CEILING_HOURS),
                ),
            ),
            4,
        )

        age_hours = hours_between(
            asset.commissioned_at or context.computed_at, context.computed_at
        )
        lifecycle = _lifecycle_stage(age_hours, economics.design_life_hours, health)

        # --- Business ---------------------------------------------------------
        # Risk score blends likelihood of failure with the consequence of it.
        consequence = min(
            1.0,
            (economics.replacement_cost + economics.downtime_cost_per_hour * 8.0)
            / 6_000.0,
        )
        risk_score = round(failure_probability * 0.6 + consequence * 0.4, 4)

        # Cost exposure: expected loss if nothing is done — replacement plus a
        # shift of downtime, weighted by how likely that outcome is.
        cost_exposure = round(
            failure_probability
            * (economics.replacement_cost + economics.downtime_cost_per_hour * 8.0),
            2,
        )

        maintenance_cost = round(
            economics.maintenance_event_cost * (1.0 if plan and plan.maintenance_due else 0.0)
            + economics.maintenance_event_cost * (window.lifetime_failures * 0.5),
            2,
        )

        # ROI of intervening: exposure avoided per unit spent.
        maintenance_roi = (
            round((cost_exposure - maintenance_cost) / maintenance_cost, 3)
            if maintenance_cost > 0
            else 0.0
        )

        # Business value: what the asset is still worth contributing, as a
        # blend of condition, availability and remaining service life.
        remaining_life = max(
            0.0, 1.0 - (age_hours / economics.design_life_hours)
        ) if economics.design_life_hours > 0 else 0.0
        business_value = round(
            economics.replacement_cost
            * (health / 100.0) * 0.5
            + economics.replacement_cost * remaining_life * 0.3
            + economics.replacement_cost * availability * 0.2,
            2,
        )

        repair_or_replace = (
            "replace"
            if lifecycle is LifecycleStage.END_OF_LIFE
            or (maintenance_roi < 0.35 and failure_probability > 0.5)
            else "repair"
        )

        criticality = _criticality(
            rated_power_w=asset.rated_power_w, risk_score=risk_score
        )
        utilization = _utilization(window)
        energy_cost = _energy_cost(window)
        lifecycle_score = _lifecycle_score(
            age_hours, economics.design_life_hours, health
        )

        # --- Direction of travel -----------------------------------------------
        # Deltas against the previous cycle. A first cycle has no predecessor,
        # so every trend is zero rather than being invented from a default —
        # "unchanged" is the only honest answer when there is nothing to
        # compare against.
        prior = previous.get(window.identity.id)
        health_trend = round(health - prior.health_index, 3) if prior else 0.0
        failure_trend = (
            float(window.lifetime_failures - prior.failure_count) if prior else 0.0
        )
        maintenance_trend = (
            round(maintenance_cost - prior.maintenance_cost, 2) if prior else 0.0
        )
        utilization_trend = (
            round(utilization - prior.utilization, 4) if prior else 0.0
        )

        results.append(
            ApmResult(
                asset_id=window.identity.id,
                computed_at=context.computed_at,
                health_index=round(health, 2),
                mtbf_hours=mtbf,
                mttr_hours=None if mttr is None else round(mttr, 2),
                availability=availability,
                reliability=reliability,
                maintainability=maintainability,
                criticality=criticality,
                lifecycle_stage=lifecycle,
                lifecycle_score=lifecycle_score,
                utilization=utilization,
                failure_count=window.lifetime_failures,
                cost_exposure=cost_exposure,
                maintenance_cost=maintenance_cost,
                energy_cost=energy_cost,
                maintenance_roi=maintenance_roi,
                risk_score=risk_score,
                business_value=business_value,
                business_impact=_business_impact(cost_exposure, criticality),
                repair_or_replace=repair_or_replace,
                health_trend=health_trend,
                failure_trend=failure_trend,
                maintenance_trend=maintenance_trend,
                utilization_trend=utilization_trend,
            )
        )

    # Rank by exposure: the asset most likely to cost the business money if
    # ignored appears first, which is the order an executive wants to see.
    results.sort(key=lambda item: (item.cost_exposure, item.risk_score), reverse=True)
    for position, result in enumerate(results, start=1):
        result.rank = position

    # Ranking within a group and within a category, from the same ordering.
    #
    # An estate-wide position alone is not actionable for someone who owns one
    # fleet: a charger sitting 90th overall can still be the worst charger in
    # the building, and that is the finding its owner needs. Because `results`
    # is already ordered by exposure, walking it once and counting per bucket
    # produces both without a second sort.
    fleet_position: dict[uuid.UUID | None, int] = {}
    type_position: dict[str, int] = {}

    for result in results:
        asset = assets.get(result.asset_id)
        if asset is None:
            continue

        group_id = asset.asset_group_id
        fleet_position[group_id] = fleet_position.get(group_id, 0) + 1
        result.fleet_rank = fleet_position[group_id]

        category = str(asset.asset_type)
        type_position[category] = type_position.get(category, 0) + 1
        result.type_rank = type_position[category]

    for result in results:
        session.add(result)

    # Lifecycle stage is durable enough to belong on the asset row, so fleet
    # queries can filter by it without joining the results table.
    for result in results:
        asset = assets.get(result.asset_id)
        if asset is not None:
            asset.lifecycle_stage = result.lifecycle_stage

    return len(results)

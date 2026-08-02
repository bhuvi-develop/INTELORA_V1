"""Cross-layer summaries.

Reads the most recent result from each layer and reduces it to the headline
verdicts the Cockpit's intelligence band and each module header display. This
is Business Intelligence work — aggregating across layers so the Presentation
Layer never has to.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnomalyResult,
    ApmResult,
    OeeResult,
    PredictiveResult,
    PrescriptiveResult,
    PreventiveResult,
)
from app.schemas.enums import (
    AlertSeverity,
    AnomalyStatus,
    BusinessImpact,
    LifecycleStage,
    RiskLevel,
    ScopeType,
)
from app.schemas.intelligence import (
    AnomalySummary,
    ApmSummary,
    IntelligenceSummary,
    OeeRead,
    OeeSummary,
    PredictiveSummary,
    PrescriptiveSummary,
    PreventiveSummary,
)
from app.services.comparison_service import (
    HIGH_RISK_THRESHOLD,
    build_comparison,
    build_enterprise_kpis,
)
from app.utils.time import start_of_utc_day, utc_now


async def _latest_computed_at(session: AsyncSession, model) -> object | None:
    """Timestamp of the most recent computation for a layer."""
    return await session.scalar(select(func.max(model.computed_at)))


async def build_anomaly_summary(session: AsyncSession) -> AnomalySummary:
    """Headline anomaly position for today."""
    day_start = start_of_utc_day()

    rows = (
        await session.execute(
            select(AnomalyResult.severity, func.count())
            .where(AnomalyResult.detected_at >= day_start)
            .group_by(AnomalyResult.severity)
        )
    ).all()
    by_severity = {severity: int(count) for severity, count in rows}

    affected = int(
        await session.scalar(
            select(func.count(func.distinct(AnomalyResult.asset_id))).where(
                AnomalyResult.detected_at >= day_start
            )
        )
        or 0
    )

    confidence = await session.scalar(
        select(func.avg(AnomalyResult.confidence)).where(
            AnomalyResult.detected_at >= day_start
        )
    )

    fault_rows = (
        await session.execute(
            select(AnomalyResult.fault_type, func.count())
            .where(AnomalyResult.detected_at >= day_start)
            .group_by(AnomalyResult.fault_type)
            .order_by(func.count().desc())
            .limit(1)
        )
    ).first()

    cause_rows = (
        await session.execute(
            select(AnomalyResult.root_cause, func.count())
            .where(AnomalyResult.detected_at >= day_start)
            .group_by(AnomalyResult.root_cause)
            .order_by(func.count().desc())
            .limit(1)
        )
    ).first()

    # Open now is a different question from raised today: a fault that started
    # yesterday and is still present is the one somebody needs to deal with.
    open_now = int(
        await session.scalar(
            select(func.count())
            .select_from(AnomalyResult)
            .where(AnomalyResult.status == AnomalyStatus.OPEN)
        )
        or 0
    )
    cleared_today = int(
        await session.scalar(
            select(func.count())
            .select_from(AnomalyResult)
            .where(
                AnomalyResult.status == AnomalyStatus.CLEARED,
                AnomalyResult.cleared_at >= day_start,
            )
        )
        or 0
    )

    return AnomalySummary(
        today=sum(by_severity.values()),
        critical=by_severity.get(AlertSeverity.CRITICAL, 0),
        warning=by_severity.get(AlertSeverity.WARNING, 0),
        information=by_severity.get(AlertSeverity.INFORMATION, 0),
        affected_assets=affected,
        top_fault_type=fault_rows[0] if fault_rows else None,
        average_confidence=round(float(confidence or 0.0), 3),
        open_now=open_now,
        cleared_today=cleared_today,
        resolved_today=cleared_today,
        top_root_cause=cause_rows[0] if cause_rows else None,
    )


async def build_predictive_summary(session: AsyncSession) -> PredictiveSummary:
    """Headline predictive position from the latest cycle."""
    latest = await _latest_computed_at(session, PredictiveResult)
    if latest is None:
        return PredictiveSummary()

    rows = (
        await session.scalars(
            select(PredictiveResult).where(PredictiveResult.computed_at == latest)
        )
    ).all()
    if not rows:
        return PredictiveSummary()

    at_risk = [r for r in rows if r.risk_level in {RiskLevel.HIGH, RiskLevel.SEVERE}]
    ruls = [
        r.remaining_useful_life_hours
        for r in rows
        if r.remaining_useful_life_hours is not None
    ]
    predicted = [r.predicted_failure_at for r in rows if r.predicted_failure_at is not None]

    return PredictiveSummary(
        assets_at_risk=len(at_risk),
        severe=sum(1 for r in rows if r.risk_level is RiskLevel.SEVERE),
        high=sum(1 for r in rows if r.risk_level is RiskLevel.HIGH),
        average_failure_probability=round(
            sum(r.failure_probability for r in rows) / len(rows), 4
        ),
        shortest_rul_hours=round(min(ruls), 2) if ruls else None,
        next_predicted_failure_at=min(predicted) if predicted else None,
        average_confidence=round(sum(r.confidence for r in rows) / len(rows), 3),
    )


async def build_preventive_summary(session: AsyncSession) -> PreventiveSummary:
    """Which assets need service, and when."""
    latest = await _latest_computed_at(session, PreventiveResult)
    if latest is None:
        return PreventiveSummary()

    rows = (
        await session.scalars(
            select(PreventiveResult).where(PreventiveResult.computed_at == latest)
        )
    ).all()
    if not rows:
        return PreventiveSummary()

    now = utc_now()
    week_ahead = now + timedelta(days=7)
    due = [r for r in rows if r.maintenance_due]
    due_dates = [r.due_at for r in rows if r.due_at is not None]

    return PreventiveSummary(
        due_now=len(due),
        due_this_week=sum(
            1 for r in rows if r.due_at is not None and r.due_at <= week_ahead
        ),
        severe_priority=sum(1 for r in rows if r.priority is RiskLevel.SEVERE),
        next_due_at=min(due_dates) if due_dates else None,
        reminders_pending=sum(
            1 for r in rows if r.reminder_at is not None and r.reminder_at <= now
        ),
        total_estimated_hours=round(
            sum(r.estimated_duration_hours or 0.0 for r in due), 2
        ),
        condition_based=sum(1 for r in rows if r.triggered_by_component is not None),
    )


async def build_prescriptive_summary(session: AsyncSession) -> PrescriptiveSummary:
    """Recommended actions and the value of taking them."""
    latest = await _latest_computed_at(session, PrescriptiveResult)
    if latest is None:
        return PrescriptiveSummary()

    rows = (
        await session.scalars(
            select(PrescriptiveResult).where(PrescriptiveResult.computed_at == latest)
        )
    ).all()
    if not rows:
        return PrescriptiveSummary()

    actionable = [
        r for r in rows if r.recommended_action.value != "continue_monitoring"
    ]
    counts = Counter(r.recommended_action for r in actionable)

    return PrescriptiveSummary(
        recommendations=len(actionable),
        total_energy_saving_kwh=round(sum(r.energy_saving_kwh for r in rows), 3),
        total_cost_saving=round(sum(r.cost_saving for r in rows), 2),
        top_action=counts.most_common(1)[0][0] if counts else None,
        critical_impact=sum(
            1 for r in actionable if r.business_impact is BusinessImpact.CRITICAL
        ),
        high_impact=sum(
            1 for r in actionable if r.business_impact is BusinessImpact.HIGH
        ),
        total_health_gain=round(sum(r.expected_health_gain for r in actionable), 1),
    )


async def build_apm_summary(session: AsyncSession) -> ApmSummary:
    """Fleet reliability and business exposure."""
    latest = await _latest_computed_at(session, ApmResult)
    if latest is None:
        return ApmSummary()

    rows = (
        await session.scalars(select(ApmResult).where(ApmResult.computed_at == latest))
    ).all()
    if not rows:
        return ApmSummary()

    count = len(rows)
    return ApmSummary(
        average_health_index=round(sum(r.health_index for r in rows) / count, 2),
        average_availability=round(sum(r.availability for r in rows) / count, 4),
        average_reliability=round(sum(r.reliability for r in rows) / count, 4),
        total_cost_exposure=round(sum(r.cost_exposure for r in rows), 2),
        total_maintenance_cost=round(sum(r.maintenance_cost for r in rows), 2),
        assets_end_of_life=sum(
            1 for r in rows if r.lifecycle_stage is LifecycleStage.END_OF_LIFE
        ),
        replace_recommended=sum(1 for r in rows if r.repair_or_replace == "replace"),
        average_utilization=round(sum(r.utilization for r in rows) / count, 4),
        average_lifecycle_score=round(sum(r.lifecycle_score for r in rows) / count, 2),
        average_maintainability=round(sum(r.maintainability for r in rows) / count, 4),
        total_energy_cost=round(sum(r.energy_cost for r in rows), 4),
        total_business_value=round(sum(r.business_value for r in rows), 2),
        critical_impact=sum(
            1 for r in rows if r.business_impact is BusinessImpact.CRITICAL
        ),
        high_impact=sum(1 for r in rows if r.business_impact is BusinessImpact.HIGH),
        high_risk_assets=sum(
            1 for r in rows if r.risk_score >= HIGH_RISK_THRESHOLD
        ),
        # Mean movement since the previous cycle: whether the fleet as a whole
        # is recovering or degrading, which no single asset's trend can say.
        mean_health_trend=round(sum(r.health_trend for r in rows) / count, 3),
    )


async def build_oee_summary(session: AsyncSession) -> OeeSummary:
    """Enterprise OEE and its breakdowns."""
    latest = await _latest_computed_at(session, OeeResult)
    if latest is None:
        return OeeSummary()

    rows = (
        await session.scalars(select(OeeResult).where(OeeResult.computed_at == latest))
    ).all()
    if not rows:
        return OeeSummary()

    def of(scope: ScopeType) -> list[OeeRead]:
        return [
            OeeRead.model_validate(row) for row in rows if row.scope_type is scope
        ]

    enterprise = of(ScopeType.ENTERPRISE)

    return OeeSummary(
        enterprise=enterprise[0] if enterprise else None,
        by_building=of(ScopeType.BUILDING),
        by_department=of(ScopeType.DEPARTMENT),
        by_fleet=of(ScopeType.FLEET),
        by_asset_type=of(ScopeType.ASSET),
    )


async def build_intelligence_summary(session: AsyncSession) -> IntelligenceSummary:
    """Every layer's headline verdict, for Cockpit section 4.

    Carries the Business Intelligence roll-ups alongside the six layer
    summaries. They travel on this payload rather than a channel of their own
    because the runner already broadcasts it after every pass, and the
    executive position is stale the moment the layers beneath it move — a
    separate channel would have to be published at the same instant anyway,
    with the added risk of the two arriving out of step.
    """
    return IntelligenceSummary(
        anomaly=await build_anomaly_summary(session),
        predictive=await build_predictive_summary(session),
        preventive=await build_preventive_summary(session),
        prescriptive=await build_prescriptive_summary(session),
        apm=await build_apm_summary(session),
        oee=await build_oee_summary(session),
        enterprise=await build_enterprise_kpis(session),
        comparison=await build_comparison(session),
    )

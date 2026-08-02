"""Intelligence Layer endpoints.

One router per layer, all in one module because they share the same shape:
fetch the newest results, join asset identity, return the envelope. Splitting
six near-identical readers across six files would duplicate the join logic six
times, which the SSOT's "never write duplicate code" rule forbids more strongly
than it asks for one file per layer.

Each layer also exposes a ``POST`` trigger so analysis can be run on demand
rather than only on the interval. All six triggers execute the same ordered
pass — the layers depend on one another, so running one in isolation would
produce results derived from stale inputs.
"""

from __future__ import annotations

import uuid
from typing import Annotated, TypeVar

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.intelligence.runner import intelligence_runner
from app.intelligence.summaries import (
    build_anomaly_summary,
    build_apm_summary,
    build_oee_summary,
    build_predictive_summary,
    build_prescriptive_summary,
    build_preventive_summary,
)
from app.models import (
    AnomalyResult,
    ApmResult,
    Asset,
    MaintenanceLog,
    OeeResult,
    PredictiveResult,
    PrescriptiveResult,
    PreventiveResult,
)
from app.routers.deps import SessionDep
from app.schemas.common import Envelope, envelope
from app.schemas.enums import (
    AnomalyStatus,
    AssetType,
    FaultType,
    MaintenanceOutcome,
    RiskLevel,
    RootCause,
    ScopeType,
    TimeRange,
)
from app.schemas.intelligence import (
    AnomalyRead,
    AnomalySummary,
    ApmRead,
    ApmSummary,
    ApmTrendPoint,
    ChecklistItem,
    ComparisonReport,
    ComponentHealthRead,
    EnterpriseKpis,
    FleetRankingEntry,
    MaintenanceCalendar,
    MaintenanceHistorySummary,
    MaintenanceLogRead,
    OeeAssetRead,
    OeeRead,
    OeeRollup,
    OeeSummary,
    OeeTrendPoint,
    PredictiveRead,
    PredictiveSummary,
    PrescriptiveRead,
    PrescriptiveSummary,
    PreventiveRead,
    PreventiveSummary,
)
from app.services.comparison_service import (
    build_comparison,
    build_enterprise_kpis,
    build_fleet_ranking,
)
from app.services.health_engine import health_engine
from app.services.performance_history import (
    ROLLUP_PERIODS,
    apm_history,
    apm_trend,
    oee_asset_latest,
    oee_asset_trend,
    oee_for_asset,
    oee_rollup,
    oee_scope_trend,
)
from app.services.intelligence_history import (
    log_to_read,
    anomaly_history,
    fault_distribution,
    maintenance_calendar,
    maintenance_history,
    maintenance_summary,
    predictive_history,
    prescriptive_history,
    root_cause_distribution,
    upcoming_maintenance,
    window_for,
)
from app.utils.time import hours_between, utc_now

ModelT = TypeVar("ModelT")


async def _latest_rows(
    session: AsyncSession,
    model: type,
    *,
    asset_id: uuid.UUID | None = None,
    asset_type: AssetType | None = None,
    limit: int = 500,
) -> list[tuple[object, Asset]]:
    """Rows from the most recent computation, joined to asset identity.

    Every layer writes a whole fleet's worth of rows stamped with the same
    ``computed_at``, so selecting that timestamp is what "latest" means here.
    """
    latest = await session.scalar(select(func.max(model.computed_at)))
    if latest is None:
        return []

    query = (
        select(model, Asset)
        .join(Asset, model.asset_id == Asset.id)
        .where(model.computed_at == latest)
        .limit(limit)
    )
    if asset_id is not None:
        query = query.where(model.asset_id == asset_id)
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    return list((await session.execute(query)).all())


def _stamp(payload: dict, asset: Asset) -> dict:
    """Attach asset identity to a result projection."""
    payload.update(
        asset_code=asset.asset_code, asset_name=asset.name, asset_type=asset.asset_type
    )
    return payload


# =============================================================================
# Layer 1 — Anomaly Detection
# =============================================================================

anomaly_router = APIRouter(prefix="/anomaly", tags=["Layer 1 · Anomaly Detection"])


@anomaly_router.get("", response_model=Envelope[list[AnomalyRead]], summary="Recent anomalies")
async def list_anomalies(
    session: SessionDep,
    asset_type: Annotated[AssetType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Envelope[list[AnomalyRead]]:
    """Newest detections across the fleet."""
    query = (
        select(AnomalyResult, Asset)
        .join(Asset, AnomalyResult.asset_id == Asset.id)
        .order_by(AnomalyResult.detected_at.desc())
        .limit(limit)
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    rows = (await session.execute(query)).all()
    return envelope(
        [
            AnomalyRead(**_stamp(AnomalyRead.model_validate(result).model_dump(), asset))
            for result, asset in rows
        ]
    )


@anomaly_router.get(
    "/summary", response_model=Envelope[AnomalySummary], summary="Anomaly headline"
)
async def anomaly_summary(session: SessionDep) -> Envelope[AnomalySummary]:
    """Today's anomaly position."""
    return envelope(await build_anomaly_summary(session))


@anomaly_router.get(
    "/history",
    response_model=Envelope[list[AnomalyRead]],
    summary="Anomaly history",
    description="Anomalies within a named range, filterable by asset type, "
    "asset, status, fault and diagnosed root cause.",
)
async def anomaly_history_endpoint(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    asset_type: Annotated[AssetType | None, Query()] = None,
    asset_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[AnomalyStatus | None, Query()] = None,
    fault_type: Annotated[FaultType | None, Query()] = None,
    root_cause: Annotated[RootCause | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 300,
) -> Envelope[list[AnomalyRead]]:
    """Historical anomalies for the selected window."""
    start, end = window_for(time_range)
    return envelope(
        await anomaly_history(
            session,
            start=start,
            end=end,
            asset_type=asset_type,
            asset_id=asset_id,
            status=status,
            fault_type=fault_type,
            root_cause=root_cause,
            limit=limit,
        )
    )


@anomaly_router.get(
    "/distribution",
    response_model=Envelope[dict[str, list]],
    summary="Fault and root-cause distribution",
    description="Anomaly counts grouped by fault type and by diagnosed cause. "
    "The cause view is the more actionable of the two: several assets showing "
    "different symptoms from one failing supply is a single job.",
)
async def anomaly_distribution(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    asset_type: Annotated[AssetType | None, Query()] = None,
) -> Envelope[dict[str, list]]:
    """Distribution of anomalies by fault and by cause."""
    start, end = window_for(time_range)
    return envelope(
        {
            "by_fault": await fault_distribution(
                session, start=start, end=end, asset_type=asset_type
            ),
            "by_root_cause": await root_cause_distribution(
                session, start=start, end=end, asset_type=asset_type
            ),
        }
    )


@anomaly_router.post(
    "/analyze", response_model=Envelope[dict[str, int]], summary="Run analysis now"
)
async def run_anomaly_analysis() -> Envelope[dict[str, int]]:
    """Trigger a full intelligence pass immediately."""
    counts = await intelligence_runner.run_cycle()
    return envelope(counts, message="Analysis complete.")


# Registered last on purpose. FastAPI matches routes in declaration order, so a
# path parameter declared above `/history` or `/distribution` would swallow
# them and reject the literal segment as a malformed UUID.
@anomaly_router.get(
    "/{asset_id}",
    response_model=Envelope[list[AnomalyRead]],
    summary="Anomalies for one asset",
)
async def anomalies_for_asset(
    asset_id: uuid.UUID,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Envelope[list[AnomalyRead]]:
    """Detection history for a single asset."""
    rows = (
        await session.execute(
            select(AnomalyResult, Asset)
            .join(Asset, AnomalyResult.asset_id == Asset.id)
            .where(AnomalyResult.asset_id == asset_id)
            .order_by(AnomalyResult.detected_at.desc())
            .limit(limit)
        )
    ).all()
    return envelope(
        [
            AnomalyRead(**_stamp(AnomalyRead.model_validate(result).model_dump(), asset))
            for result, asset in rows
        ]
    )


# =============================================================================
# Layer 2 — Predictive Maintenance
# =============================================================================

predictive_router = APIRouter(
    prefix="/predictive", tags=["Layer 2 · Predictive Maintenance"]
)


@predictive_router.get(
    "", response_model=Envelope[list[PredictiveRead]], summary="Failure predictions"
)
async def list_predictions(
    session: SessionDep,
    asset_type: Annotated[AssetType | None, Query()] = None,
    risk: Annotated[RiskLevel | None, Query()] = None,
) -> Envelope[list[PredictiveRead]]:
    """Latest prediction per asset, highest risk first."""
    rows = await _latest_rows(session, PredictiveResult, asset_type=asset_type)
    order = {
        RiskLevel.SEVERE: 0,
        RiskLevel.HIGH: 1,
        RiskLevel.MODERATE: 2,
        RiskLevel.LOW: 3,
    }

    results = [
        PredictiveRead(**_stamp(PredictiveRead.model_validate(result).model_dump(), asset))
        for result, asset in rows
        if risk is None or result.risk_level is risk
    ]
    results.sort(key=lambda item: (order[item.risk_level], -item.failure_probability))
    return envelope(results)


@predictive_router.get(
    "/summary", response_model=Envelope[PredictiveSummary], summary="Predictive headline"
)
async def predictive_summary(session: SessionDep) -> Envelope[PredictiveSummary]:
    """Fleet-level predictive position."""
    return envelope(await build_predictive_summary(session))


@predictive_router.get(
    "/history",
    response_model=Envelope[list[PredictiveRead]],
    summary="Prediction history",
    description="How the forecast for an asset has evolved. Tracking the "
    "trajectory of a prediction matters as much as its current value — a "
    "failure probability climbing steadily is a different situation from one "
    "that has been flat for a week.",
)
async def predictive_history_endpoint(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    asset_id: Annotated[uuid.UUID | None, Query()] = None,
    asset_type: Annotated[AssetType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 300,
) -> Envelope[list[PredictiveRead]]:
    """Historical predictions for the selected window."""
    start, end = window_for(time_range)
    return envelope(
        await predictive_history(
            session,
            start=start,
            end=end,
            asset_id=asset_id,
            asset_type=asset_type,
            limit=limit,
        )
    )


@predictive_router.get(
    "/{asset_id}/components",
    response_model=Envelope[list[ComponentHealthRead]],
    summary="Component health for one asset",
    description="Per-subsystem condition from the newest prediction. A single "
    "score says whether to worry; this says which part to look at.",
)
async def asset_components(
    asset_id: uuid.UUID, session: SessionDep
) -> Envelope[list[ComponentHealthRead]]:
    """Subsystem breakdown for one asset."""
    rows = await _latest_rows(session, PredictiveResult, asset_id=asset_id, limit=1)
    if not rows:
        return envelope([], message="No prediction computed for this asset yet.")

    result, _ = rows[0]
    return envelope(
        [ComponentHealthRead(**item) for item in (result.component_health or [])]
    )


@predictive_router.post(
    "/run", response_model=Envelope[dict[str, int]], summary="Run predictions now"
)
async def run_predictions() -> Envelope[dict[str, int]]:
    """Trigger a full intelligence pass immediately."""
    counts = await intelligence_runner.run_cycle()
    return envelope(counts, message="Predictions recomputed.")


# =============================================================================
# Layer 3 — Preventive Maintenance (no page; surfaces inside Predictive and APM)
# =============================================================================

preventive_router = APIRouter(
    prefix="/preventive", tags=["Layer 3 · Preventive Maintenance"]
)


@preventive_router.get(
    "", response_model=Envelope[list[PreventiveRead]], summary="Maintenance schedule"
)
async def list_maintenance(
    session: SessionDep,
    asset_type: Annotated[AssetType | None, Query()] = None,
    due_only: Annotated[bool, Query()] = False,
) -> Envelope[list[PreventiveRead]]:
    """Latest maintenance recommendation per asset, soonest first."""
    rows = await _latest_rows(session, PreventiveResult, asset_type=asset_type)
    results = [
        PreventiveRead(**_stamp(PreventiveRead.model_validate(result).model_dump(), asset))
        for result, asset in rows
        if not due_only or result.maintenance_due
    ]
    results.sort(key=lambda item: (item.due_at is None, item.due_at))
    return envelope(results)


@preventive_router.get(
    "/summary", response_model=Envelope[PreventiveSummary], summary="Maintenance headline"
)
async def preventive_summary(session: SessionDep) -> Envelope[PreventiveSummary]:
    """Which devices require maintenance, and when."""
    return envelope(await build_preventive_summary(session))


@preventive_router.get(
    "/upcoming",
    response_model=Envelope[list[PreventiveRead]],
    summary="Upcoming maintenance",
    description="Plans whose service window opens within the horizon, soonest "
    "first. Reads the newest computation only — older plans for the same asset "
    "are superseded and would double-book the schedule.",
)
async def upcoming(
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=120)] = 14,
    asset_type: Annotated[AssetType | None, Query()] = None,
) -> Envelope[list[PreventiveRead]]:
    """Work coming up in the next ``days``."""
    return envelope(
        await upcoming_maintenance(session, days=days, asset_type=asset_type)
    )


@preventive_router.get(
    "/calendar",
    response_model=Envelope[MaintenanceCalendar],
    summary="Maintenance calendar",
    description="Scheduled work grouped by day, with a load estimate per day. "
    "Grouped server-side so every client agrees on day boundaries.",
)
async def calendar(
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=180)] = 30,
    asset_type: Annotated[AssetType | None, Query()] = None,
) -> Envelope[MaintenanceCalendar]:
    """Day-by-day view of scheduled maintenance."""
    return envelope(
        await maintenance_calendar(session, days=days, asset_type=asset_type)
    )


@preventive_router.get(
    "/history",
    response_model=Envelope[list[MaintenanceLogRead]],
    summary="Maintenance history",
    description="Recorded maintenance activity within a named range.",
)
async def maintenance_history_endpoint(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.LAST_30_DAYS,
    asset_type: Annotated[AssetType | None, Query()] = None,
    asset_id: Annotated[uuid.UUID | None, Query()] = None,
    outcome: Annotated[MaintenanceOutcome | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 300,
) -> Envelope[list[MaintenanceLogRead]]:
    """What work was scheduled or performed in the window."""
    start, end = window_for(time_range)
    return envelope(
        await maintenance_history(
            session,
            start=start,
            end=end,
            asset_type=asset_type,
            asset_id=asset_id,
            outcome=outcome,
            limit=limit,
        )
    )


@preventive_router.get(
    "/history/summary",
    response_model=Envelope[MaintenanceHistorySummary],
    summary="Maintenance history summary",
    description="Completion counts, mean duration and mean health recovered — "
    "the return on maintenance actually performed.",
)
async def maintenance_history_summary(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.LAST_30_DAYS,
    asset_type: Annotated[AssetType | None, Query()] = None,
) -> Envelope[MaintenanceHistorySummary]:
    """Aggregate view of recorded maintenance."""
    start, end = window_for(time_range)
    return envelope(
        await maintenance_summary(
            session, start=start, end=end, asset_type=asset_type
        )
    )


class MaintenanceUpdate(BaseModel):
    """Operator update to a maintenance record."""

    outcome: MaintenanceOutcome
    performed_by: str | None = Field(default=None, max_length=160)
    notes: str | None = None
    cost: float | None = Field(default=None, ge=0)
    checklist: list[ChecklistItem] | None = None


@preventive_router.put(
    "/history/{log_id}",
    response_model=Envelope[MaintenanceLogRead],
    summary="Update a maintenance record",
    description="Start, complete, defer or cancel scheduled work. Completing a "
    "job stamps the duration and captures the asset's health at that moment, "
    "which is what makes MTTR and maintenance ROI computable at all — without "
    "it the platform schedules work forever and never learns whether it helped.",
)
async def update_maintenance(
    log_id: uuid.UUID, payload: MaintenanceUpdate, session: SessionDep
) -> Envelope[MaintenanceLogRead]:
    """Record progress against a maintenance job."""
    log = await session.get(MaintenanceLog, log_id)
    if log is None:
        raise NotFoundError(f"Maintenance record {log_id} does not exist.")

    now = utc_now()
    previous = log.outcome
    log.outcome = payload.outcome

    if payload.outcome is MaintenanceOutcome.IN_PROGRESS and log.started_at is None:
        log.started_at = now

    if payload.outcome is MaintenanceOutcome.COMPLETED:
        log.completed_at = now
        if log.started_at is None:
            log.started_at = now
        log.duration_hours = round(hours_between(log.started_at, now), 4)
        # Health at completion, so the value of the work is measured rather
        # than assumed. Read live: the asset has just been serviced.
        current = health_engine.current(log.asset_id)
        if current is not None:
            log.health_after = round(current, 2)

    if payload.performed_by is not None:
        log.performed_by = payload.performed_by.strip() or None
    if payload.notes is not None:
        log.notes = payload.notes
    if payload.cost is not None:
        log.cost = payload.cost
    if payload.checklist is not None:
        log.checklist = [item.model_dump() for item in payload.checklist]

    await session.commit()

    asset = await session.get(Asset, log.asset_id)
    if asset is None:
        raise NotFoundError("The asset this record refers to no longer exists.")

    return envelope(
        log_to_read(log, asset),
        message=f"Maintenance moved from {previous.value} to {payload.outcome.value}.",
    )


@preventive_router.post(
    "/generate", response_model=Envelope[dict[str, int]], summary="Regenerate schedule"
)
async def generate_maintenance() -> Envelope[dict[str, int]]:
    """Trigger a full intelligence pass immediately."""
    counts = await intelligence_runner.run_cycle()
    return envelope(counts, message="Maintenance schedule regenerated.")


# =============================================================================
# Layer 4 — Prescriptive Optimisation (advisory only)
# =============================================================================

prescriptive_router = APIRouter(
    prefix="/prescriptive", tags=["Layer 4 · Prescriptive Optimisation"]
)


@prescriptive_router.get(
    "", response_model=Envelope[list[PrescriptiveRead]], summary="Recommendations"
)
async def list_recommendations(
    session: SessionDep,
    asset_type: Annotated[AssetType | None, Query()] = None,
    actionable_only: Annotated[bool, Query()] = True,
) -> Envelope[list[PrescriptiveRead]]:
    """Latest recommendation per asset, highest value first.

    All output is advisory. The platform recommends; it never commands.
    """
    rows = await _latest_rows(session, PrescriptiveResult, asset_type=asset_type)
    results = [
        PrescriptiveRead(
            **_stamp(PrescriptiveRead.model_validate(result).model_dump(), asset)
        )
        for result, asset in rows
        if not actionable_only or result.recommended_action.value != "continue_monitoring"
    ]
    results.sort(key=lambda item: item.cost_saving, reverse=True)
    return envelope(results)


@prescriptive_router.get(
    "/summary",
    response_model=Envelope[PrescriptiveSummary],
    summary="Optimisation headline",
)
async def prescriptive_summary(session: SessionDep) -> Envelope[PrescriptiveSummary]:
    """Recommended actions and the value of taking them."""
    return envelope(await build_prescriptive_summary(session))


@prescriptive_router.get(
    "/history",
    response_model=Envelope[list[PrescriptiveRead]],
    summary="Recommendation history",
    description="Recommendations issued within a named range, so the value of "
    "advice given can be reviewed against what was actually done.",
)
async def prescriptive_history_endpoint(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    asset_type: Annotated[AssetType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 300,
) -> Envelope[list[PrescriptiveRead]]:
    """Historical recommendations for the selected window."""
    start, end = window_for(time_range)
    return envelope(
        await prescriptive_history(
            session, start=start, end=end, asset_type=asset_type, limit=limit
        )
    )


@prescriptive_router.post(
    "/recommend", response_model=Envelope[dict[str, int]], summary="Recompute advice"
)
async def recommend() -> Envelope[dict[str, int]]:
    """Trigger a full intelligence pass immediately."""
    counts = await intelligence_runner.run_cycle()
    return envelope(counts, message="Recommendations recomputed.")


# =============================================================================
# Layer 5 — Asset Performance Management
# =============================================================================

apm_router = APIRouter(prefix="/apm", tags=["Layer 5 · Asset Performance Management"])


@apm_router.get("", response_model=Envelope[list[ApmRead]], summary="APM results")
async def list_apm(
    session: SessionDep,
    asset_type: Annotated[AssetType | None, Query()] = None,
) -> Envelope[list[ApmRead]]:
    """Latest APM result per asset, ranked by cost exposure."""
    rows = await _latest_rows(session, ApmResult, asset_type=asset_type)
    results = [
        ApmRead(**_stamp(ApmRead.model_validate(result).model_dump(), asset))
        for result, asset in rows
    ]
    results.sort(key=lambda item: item.rank or 10_000)
    return envelope(results)


@apm_router.get("/summary", response_model=Envelope[ApmSummary], summary="APM headline")
async def apm_summary(session: SessionDep) -> Envelope[ApmSummary]:
    """Fleet reliability and business exposure."""
    return envelope(await build_apm_summary(session))


@apm_router.get(
    "/ranking", response_model=Envelope[list[ApmRead]], summary="Asset ranking"
)
async def apm_ranking(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 15,
) -> Envelope[list[ApmRead]]:
    """The assets most likely to cost money if left alone."""
    rows = await _latest_rows(session, ApmResult)
    results = [
        ApmRead(**_stamp(ApmRead.model_validate(result).model_dump(), asset))
        for result, asset in rows
    ]
    results.sort(key=lambda item: item.rank or 10_000)
    return envelope(results[:limit])


@apm_router.get(
    "/history",
    response_model=Envelope[list[ApmRead]],
    summary="APM history",
    description="Individual APM results within a named range. Answers "
    "\"what did this asset look like at the time\", as opposed to the trend "
    "endpoint's \"how has it moved\".",
)
async def apm_history_endpoint(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    asset_id: Annotated[uuid.UUID | None, Query()] = None,
    asset_type: Annotated[AssetType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 300,
) -> Envelope[list[ApmRead]]:
    """Historical APM results for the selected window."""
    start, end = window_for(time_range)
    return envelope(
        await apm_history(
            session,
            start=start,
            end=end,
            asset_id=asset_id,
            asset_type=asset_type,
            limit=limit,
        )
    )


@apm_router.get(
    "/trend",
    response_model=Envelope[list[ApmTrendPoint]],
    summary="APM trend",
    description="Health, availability, reliability, utilisation, risk and cost "
    "over time, averaged across the selected assets. With no filter this is "
    "the fleet trajectory; with an asset selected it is that asset's own.",
)
async def apm_trend_endpoint(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    asset_id: Annotated[uuid.UUID | None, Query()] = None,
    asset_type: Annotated[AssetType | None, Query()] = None,
    points: Annotated[int, Query(ge=2, le=1000)] = 240,
) -> Envelope[list[ApmTrendPoint]]:
    """APM measures over time."""
    start, end = window_for(time_range)
    return envelope(
        await apm_trend(
            session,
            start=start,
            end=end,
            asset_id=asset_id,
            asset_type=asset_type,
            points=points,
        )
    )


@apm_router.get(
    "/comparison",
    response_model=Envelope[ComparisonReport | None],
    summary="Category comparison",
    description="Compares laptop chargers, mobile chargers and air "
    "conditioners on normalised business KPIs. Raw telemetry is never "
    "compared: an air conditioner draws 5.2 kW and a mobile charger 33 W, so "
    "ranking them on power measures nameplate rather than performance.",
)
async def apm_comparison(session: SessionDep) -> Envelope[ComparisonReport | None]:
    """Executive comparison across asset categories."""
    report = await build_comparison(session)
    if report is None:
        return envelope(None, message="No comparison available until the first pass.")
    return envelope(report)


@apm_router.get(
    "/fleet-ranking",
    response_model=Envelope[list[FleetRankingEntry]],
    summary="Fleet ranking",
    description="Asset groups ranked against each other. A fleet is what an "
    "operations manager actually owns, so this is the level at which an "
    "estate-wide figure becomes somebody's to-do list.",
)
async def apm_fleet_ranking(session: SessionDep) -> Envelope[list[FleetRankingEntry]]:
    """Asset groups ordered by composite standing."""
    return envelope(await build_fleet_ranking(session))


@apm_router.get(
    "/enterprise",
    response_model=Envelope[EnterpriseKpis | None],
    summary="Enterprise KPIs",
    description="The executive position across every layer in one payload: "
    "enterprise health and OEE, critical and high-risk counts, maintenance "
    "due, energy efficiency, cost exposure, business value, and both rankings.",
)
async def apm_enterprise(session: SessionDep) -> Envelope[EnterpriseKpis | None]:
    """Cross-layer executive summary."""
    kpis = await build_enterprise_kpis(session)
    if kpis is None:
        return envelope(None, message="No results computed yet.")
    return envelope(kpis)


@apm_router.get(
    "/{asset_id}/trend",
    response_model=Envelope[list[ApmTrendPoint]],
    summary="APM trend for one asset",
    description="The drill-down trajectory for a single asset.",
)
async def apm_asset_trend(
    asset_id: uuid.UUID,
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    points: Annotated[int, Query(ge=2, le=1000)] = 240,
) -> Envelope[list[ApmTrendPoint]]:
    """One asset's APM history as a series."""
    start, end = window_for(time_range)
    return envelope(
        await apm_trend(
            session, start=start, end=end, asset_id=asset_id, points=points
        )
    )


# Registered last on purpose, for the same reason as the anomaly router above:
# a path parameter declared before the literal segments would swallow
# `/history`, `/trend`, `/comparison`, `/fleet-ranking` and `/enterprise` and
# reject each of them as a malformed UUID.
@apm_router.get(
    "/{asset_id}", response_model=Envelope[ApmRead | None], summary="APM for one asset"
)
async def apm_for_asset(
    asset_id: uuid.UUID, session: SessionDep
) -> Envelope[ApmRead | None]:
    """Latest APM result for a single asset."""
    rows = await _latest_rows(session, ApmResult, asset_id=asset_id, limit=1)
    if not rows:
        return envelope(None, message="No APM result computed for this asset yet.")
    result, asset = rows[0]
    return envelope(ApmRead(**_stamp(ApmRead.model_validate(result).model_dump(), asset)))


# =============================================================================
# Layer 6 — Overall Equipment Efficiency
# =============================================================================

oee_router = APIRouter(prefix="/oee", tags=["Layer 6 · Overall Equipment Efficiency"])


@oee_router.get("", response_model=Envelope[OeeSummary], summary="OEE overview")
async def get_oee(session: SessionDep) -> Envelope[OeeSummary]:
    """Enterprise OEE with every breakdown."""
    return envelope(await build_oee_summary(session))


@oee_router.get(
    "/overview", response_model=Envelope[OeeSummary], summary="OEE overview (alias)"
)
async def get_oee_overview(session: SessionDep) -> Envelope[OeeSummary]:
    """Alias retained for API compatibility with the published contract."""
    return envelope(await build_oee_summary(session))


@oee_router.get(
    "/history", response_model=Envelope[list[OeeRead]], summary="OEE history"
)
async def get_oee_history(
    session: SessionDep,
    scope: Annotated[ScopeType, Query()] = ScopeType.ENTERPRISE,
    limit: Annotated[int, Query(ge=2, le=500)] = 120,
) -> Envelope[list[OeeRead]]:
    """Historical OEE at one scope, oldest first for charting."""
    rows = (
        await session.scalars(
            select(OeeResult)
            .where(OeeResult.scope_type == scope)
            .order_by(OeeResult.computed_at.desc())
            .limit(limit)
        )
    ).all()
    return envelope([OeeRead.model_validate(row) for row in reversed(rows)])


@oee_router.get(
    "/assets",
    response_model=Envelope[list[OeeAssetRead]],
    summary="OEE per asset",
    description="Every asset's own OEE, best first. This is the level all the "
    "scope rollups are built from, and the only one at which \"why is this "
    "number low\" has a concrete answer.",
)
async def oee_assets(
    session: SessionDep,
    asset_type: Annotated[AssetType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> Envelope[list[OeeAssetRead]]:
    """Latest per-asset OEE across the fleet."""
    return envelope(
        await oee_asset_latest(session, asset_type=asset_type, limit=limit)
    )


@oee_router.get(
    "/trend",
    response_model=Envelope[list[OeeTrendPoint]],
    summary="OEE trend",
    description="OEE and its three factors over time at an aggregation scope. "
    "Omit `scope_label` to average every entity at that level, or supply one "
    "to follow a single building, department or fleet.",
)
async def oee_trend(
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    scope: Annotated[ScopeType, Query()] = ScopeType.ENTERPRISE,
    scope_label: Annotated[str | None, Query()] = None,
    asset_type: Annotated[AssetType | None, Query()] = None,
    points: Annotated[int, Query(ge=2, le=1000)] = 240,
) -> Envelope[list[OeeTrendPoint]]:
    """Efficiency trajectory at one scope."""
    start, end = window_for(time_range)
    return envelope(
        await oee_scope_trend(
            session,
            start=start,
            end=end,
            scope=scope,
            scope_label=scope_label,
            asset_type=asset_type,
            points=points,
        )
    )


@oee_router.get(
    "/rollup",
    response_model=Envelope[list[OeeRollup]],
    summary="Daily, weekly and monthly OEE",
    description="OEE averaged into calendar buckets. Bucketing runs in "
    "PostgreSQL: a month of fifteen-second computations is around 170,000 rows "
    "per scope, and averaging those in the browser would transfer two orders "
    "of magnitude more data than the chart draws. Each bucket reports how many "
    "computations it averaged, so a partial period is visibly partial.",
)
async def oee_rollup_endpoint(
    session: SessionDep,
    period: Annotated[str, Query(pattern="^(daily|weekly|monthly)$")] = "daily",
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.LAST_30_DAYS,
    scope: Annotated[ScopeType, Query()] = ScopeType.ENTERPRISE,
    asset_type: Annotated[AssetType | None, Query()] = None,
) -> Envelope[list[OeeRollup]]:
    """Calendar-bucketed OEE."""
    start, end = window_for(time_range)
    return envelope(
        await oee_rollup(
            session,
            start=start,
            end=end,
            period=period,
            scope=scope,
            asset_type=asset_type,
        ),
        message=f"Bucketed by {ROLLUP_PERIODS[period]}.",
    )


@oee_router.get(
    "/asset/{asset_id}",
    response_model=Envelope[OeeAssetRead | None],
    summary="OEE for one asset",
)
async def oee_single_asset(
    asset_id: uuid.UUID, session: SessionDep
) -> Envelope[OeeAssetRead | None]:
    """Latest OEE for a single asset."""
    result = await oee_for_asset(session, asset_id)
    if result is None:
        return envelope(None, message="No OEE computed for this asset yet.")
    return envelope(result)


@oee_router.get(
    "/asset/{asset_id}/trend",
    response_model=Envelope[list[OeeTrendPoint]],
    summary="OEE trend for one asset",
    description="Read from the per-asset table rather than reconstructed from "
    "a rollup, which cannot be done — an average has already discarded the "
    "individual terms that produced it.",
)
async def oee_single_asset_trend(
    asset_id: uuid.UUID,
    session: SessionDep,
    time_range: Annotated[TimeRange, Query(alias="range")] = TimeRange.TODAY,
    points: Annotated[int, Query(ge=2, le=1000)] = 240,
) -> Envelope[list[OeeTrendPoint]]:
    """One asset's efficiency trajectory."""
    start, end = window_for(time_range)
    return envelope(
        await oee_asset_trend(
            session, asset_id=asset_id, start=start, end=end, points=points
        )
    )

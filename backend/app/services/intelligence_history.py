"""Historical intelligence queries.

Every intelligence layer writes an append-only result table, which makes
"what did the platform think last Tuesday" answerable — but only if something
knows how to ask. This module is that layer: named time ranges, asset-type
filtering and the aggregations the history views need, in one place rather than
repeated across four routers.

Range resolution is shared with telemetry history
(:mod:`app.services.history_service`) so "last 7 days" means the same window
whichever module the user is looking at. Intelligence results are written every
fifteen seconds rather than every second, so they are read from their own
tables directly — there is no rollup tier here and none is needed.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnomalyResult,
    Asset,
    MaintenanceLog,
    PredictiveResult,
    PrescriptiveResult,
    PreventiveResult,
)
from app.schemas.enums import (
    AnomalyStatus,
    AssetType,
    FaultType,
    MaintenanceOutcome,
    RiskLevel,
    RootCause,
    TimeRange,
)
from app.schemas.intelligence import (
    AnomalyRead,
    ChecklistItem,
    FaultBreakdown,
    MaintenanceCalendar,
    MaintenanceCalendarDay,
    MaintenanceHistorySummary,
    MaintenanceLogRead,
    PredictiveRead,
    PrescriptiveRead,
    PreventiveRead,
    RootCauseBreakdown,
)
from app.services.history_service import resolve_range
from app.utils.time import utc_now


def humanise(value: str) -> str:
    """Turn a snake_case enum value into a readable label."""
    return value.replace("_", " ").title()


def _stamp(payload: dict, asset: Asset) -> dict:
    """Attach asset identity to a result projection."""
    payload.update(
        asset_code=asset.asset_code,
        asset_name=asset.name,
        asset_type=asset.asset_type,
    )
    return payload


def window_for(
    time_range: TimeRange | None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Resolve a query window from a named range or explicit bounds."""
    if start is not None and end is not None:
        return (start, end) if start <= end else (end, start)
    if time_range is not None:
        return resolve_range(time_range)
    reference = utc_now()
    return reference - timedelta(hours=1), reference


# --- Layer 1: anomaly history --------------------------------------------------


async def anomaly_history(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_type: AssetType | None = None,
    asset_id: uuid.UUID | None = None,
    status: AnomalyStatus | None = None,
    fault_type: FaultType | None = None,
    root_cause: RootCause | None = None,
    limit: int = 500,
) -> list[AnomalyRead]:
    """Anomalies detected within a window, newest first."""
    query = (
        select(AnomalyResult, Asset)
        .join(Asset, AnomalyResult.asset_id == Asset.id)
        .where(AnomalyResult.detected_at >= start, AnomalyResult.detected_at <= end)
        .order_by(AnomalyResult.detected_at.desc())
        .limit(limit)
    )

    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)
    if asset_id is not None:
        query = query.where(AnomalyResult.asset_id == asset_id)
    if status is not None:
        query = query.where(AnomalyResult.status == status)
    if fault_type is not None:
        query = query.where(AnomalyResult.fault_type == fault_type)
    if root_cause is not None:
        query = query.where(AnomalyResult.root_cause == root_cause)

    rows = (await session.execute(query)).all()
    return [
        AnomalyRead(**_stamp(AnomalyRead.model_validate(result).model_dump(), asset))
        for result, asset in rows
    ]


async def fault_distribution(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_type: AssetType | None = None,
) -> list[FaultBreakdown]:
    """Anomaly counts per fault type, for the distribution view."""
    query = (
        select(
            AnomalyResult.fault_type,
            func.count().label("total"),
            func.count(AnomalyResult.id)
            .filter(AnomalyResult.severity == "critical")
            .label("critical"),
            func.count(AnomalyResult.id)
            .filter(AnomalyResult.severity == "warning")
            .label("warning"),
        )
        .join(Asset, AnomalyResult.asset_id == Asset.id)
        .where(AnomalyResult.detected_at >= start, AnomalyResult.detected_at <= end)
        .group_by(AnomalyResult.fault_type)
        .order_by(func.count().desc())
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    return [
        FaultBreakdown(
            fault_type=row.fault_type,
            label=humanise(str(row.fault_type)),
            count=int(row.total),
            critical=int(row.critical or 0),
            warning=int(row.warning or 0),
        )
        for row in (await session.execute(query)).all()
    ]


async def root_cause_distribution(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_type: AssetType | None = None,
) -> list[RootCauseBreakdown]:
    """Anomaly counts per diagnosed cause.

    More actionable than the fault breakdown: five assets reporting different
    symptoms from one failing distribution board is a single job, and only the
    cause view makes that visible.
    """
    query = (
        select(
            AnomalyResult.root_cause,
            func.count().label("total"),
            func.count(func.distinct(AnomalyResult.asset_id)).label("assets"),
        )
        .join(Asset, AnomalyResult.asset_id == Asset.id)
        .where(AnomalyResult.detected_at >= start, AnomalyResult.detected_at <= end)
        .group_by(AnomalyResult.root_cause)
        .order_by(func.count().desc())
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    return [
        RootCauseBreakdown(
            root_cause=row.root_cause,
            label=humanise(str(row.root_cause)),
            count=int(row.total),
            affected_assets=int(row.assets or 0),
        )
        for row in (await session.execute(query)).all()
    ]


# --- Layers 2 to 4: result history ----------------------------------------------


async def predictive_history(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_id: uuid.UUID | None = None,
    asset_type: AssetType | None = None,
    limit: int = 500,
) -> list[PredictiveRead]:
    """Predictions computed within a window."""
    query = (
        select(PredictiveResult, Asset)
        .join(Asset, PredictiveResult.asset_id == Asset.id)
        .where(
            PredictiveResult.computed_at >= start, PredictiveResult.computed_at <= end
        )
        .order_by(PredictiveResult.computed_at.desc())
        .limit(limit)
    )
    if asset_id is not None:
        query = query.where(PredictiveResult.asset_id == asset_id)
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    rows = (await session.execute(query)).all()
    return [
        PredictiveRead(
            **_stamp(PredictiveRead.model_validate(result).model_dump(), asset)
        )
        for result, asset in rows
    ]


async def prescriptive_history(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_type: AssetType | None = None,
    limit: int = 500,
) -> list[PrescriptiveRead]:
    """Recommendations issued within a window."""
    query = (
        select(PrescriptiveResult, Asset)
        .join(Asset, PrescriptiveResult.asset_id == Asset.id)
        .where(
            PrescriptiveResult.computed_at >= start,
            PrescriptiveResult.computed_at <= end,
        )
        .order_by(PrescriptiveResult.computed_at.desc())
        .limit(limit)
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    rows = (await session.execute(query)).all()
    return [
        PrescriptiveRead(
            **_stamp(PrescriptiveRead.model_validate(result).model_dump(), asset)
        )
        for result, asset in rows
    ]


async def upcoming_maintenance(
    session: AsyncSession,
    *,
    days: int = 14,
    asset_type: AssetType | None = None,
) -> list[PreventiveRead]:
    """Plans whose service window opens within the next ``days``.

    Reads the newest computation only. Older plans for the same asset are
    superseded, and showing them would double-book the calendar.
    """
    latest = await session.scalar(select(func.max(PreventiveResult.computed_at)))
    if latest is None:
        return []

    horizon = utc_now() + timedelta(days=days)
    query = (
        select(PreventiveResult, Asset)
        .join(Asset, PreventiveResult.asset_id == Asset.id)
        .where(
            PreventiveResult.computed_at == latest,
            PreventiveResult.window_start.isnot(None),
            PreventiveResult.window_start <= horizon,
        )
        .order_by(PreventiveResult.window_start)
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    rows = (await session.execute(query)).all()
    return [
        PreventiveRead(
            **_stamp(PreventiveRead.model_validate(result).model_dump(), asset)
        )
        for result, asset in rows
    ]


# --- Maintenance history and calendar --------------------------------------------


def log_to_read(log: MaintenanceLog, asset: Asset) -> MaintenanceLogRead:
    """Project a maintenance record, computing the health gain."""
    return MaintenanceLogRead(
        id=log.id,
        asset_id=log.asset_id,
        asset_code=asset.asset_code,
        asset_name=asset.name,
        asset_type=asset.asset_type,
        task_type=log.task_type,
        title=log.title,
        description=log.description,
        priority=log.priority,
        outcome=log.outcome,
        scheduled_for=log.scheduled_for,
        window_end=log.window_end,
        started_at=log.started_at,
        completed_at=log.completed_at,
        duration_hours=log.duration_hours,
        checklist=[ChecklistItem(**item) for item in (log.checklist or [])],
        performed_by=log.performed_by,
        notes=log.notes,
        cost=log.cost,
        health_before=log.health_before,
        health_after=log.health_after,
        health_gain=log.health_gain,
    )


async def maintenance_history(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_type: AssetType | None = None,
    asset_id: uuid.UUID | None = None,
    outcome: MaintenanceOutcome | None = None,
    limit: int = 500,
) -> list[MaintenanceLogRead]:
    """Maintenance activity within a window.

    Filtered on ``scheduled_for`` rather than creation time, because the
    question is always "what work happened when", not "when was the record
    written".
    """
    # Matched on any of three dates, not just the scheduled one.
    #
    # Filtering on `scheduled_for` alone silently returns nothing: work is
    # planned into the future while every named range looks backward from now,
    # so a fleet with eighty outstanding jobs reports an empty history. A
    # record belongs to a window if it was raised in it, worked in it, or
    # finished in it.
    query = (
        select(MaintenanceLog, Asset)
        .join(Asset, MaintenanceLog.asset_id == Asset.id)
        .where(
            or_(
                and_(
                    MaintenanceLog.scheduled_for >= start,
                    MaintenanceLog.scheduled_for <= end,
                ),
                and_(
                    MaintenanceLog.completed_at >= start,
                    MaintenanceLog.completed_at <= end,
                ),
                and_(
                    MaintenanceLog.created_at >= start,
                    MaintenanceLog.created_at <= end,
                ),
            )
        )
        .order_by(MaintenanceLog.created_at.desc())
        .limit(limit)
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)
    if asset_id is not None:
        query = query.where(MaintenanceLog.asset_id == asset_id)
    if outcome is not None:
        query = query.where(MaintenanceLog.outcome == outcome)

    rows = (await session.execute(query)).all()
    return [log_to_read(log, asset) for log, asset in rows]


async def maintenance_calendar(
    session: AsyncSession,
    *,
    days: int = 30,
    asset_type: AssetType | None = None,
) -> MaintenanceCalendar:
    """Scheduled work grouped by day.

    Grouping happens here rather than in the browser so every client sees the
    same day boundaries — a calendar that silently reinterprets UTC per
    timezone would double-book across midnight.
    """
    now = utc_now()
    horizon = now + timedelta(days=days)

    query = (
        select(MaintenanceLog, Asset)
        .join(Asset, MaintenanceLog.asset_id == Asset.id)
        .where(
            MaintenanceLog.scheduled_for.isnot(None),
            MaintenanceLog.scheduled_for >= now - timedelta(days=1),
            MaintenanceLog.scheduled_for <= horizon,
            MaintenanceLog.outcome.in_(
                (MaintenanceOutcome.SCHEDULED, MaintenanceOutcome.IN_PROGRESS)
            ),
        )
        .order_by(MaintenanceLog.scheduled_for)
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    rows = (await session.execute(query)).all()

    grouped: dict[date, list[MaintenanceLogRead]] = defaultdict(list)
    for log, asset in rows:
        if log.scheduled_for is None:
            continue
        grouped[log.scheduled_for.date()].append(log_to_read(log, asset))

    calendar_days: list[MaintenanceCalendarDay] = []
    total_hours = 0.0

    for day in sorted(grouped):
        entries = grouped[day]
        # A scheduled entry has no measured duration yet, so the estimate falls
        # back to the checklist length. Quarter of an hour per step is rough,
        # but a calendar with no load estimate at all cannot be planned against.
        hours = sum(
            entry.duration_hours or len(entry.checklist) * 0.25 for entry in entries
        )
        total_hours += hours

        calendar_days.append(
            MaintenanceCalendarDay(
                date=day,
                total=len(entries),
                severe=sum(1 for e in entries if e.priority is RiskLevel.SEVERE),
                high=sum(1 for e in entries if e.priority is RiskLevel.HIGH),
                estimated_hours=round(hours, 2),
                entries=entries,
            )
        )

    return MaintenanceCalendar(
        start=now.date(),
        end=horizon.date(),
        days=calendar_days,
        total_scheduled=sum(day.total for day in calendar_days),
        total_estimated_hours=round(total_hours, 2),
    )


async def maintenance_summary(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_type: AssetType | None = None,
) -> MaintenanceHistorySummary:
    """What has actually been done within a window."""
    query = (
        select(MaintenanceLog)
        .join(Asset, MaintenanceLog.asset_id == Asset.id)
        .where(
            or_(
                and_(
                    MaintenanceLog.scheduled_for >= start,
                    MaintenanceLog.scheduled_for <= end,
                ),
                and_(
                    MaintenanceLog.completed_at >= start,
                    MaintenanceLog.completed_at <= end,
                ),
                and_(
                    MaintenanceLog.created_at >= start,
                    MaintenanceLog.created_at <= end,
                ),
            )
        )
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)

    rows = list((await session.scalars(query)).all())
    if not rows:
        return MaintenanceHistorySummary()

    outcomes = Counter(row.outcome for row in rows)
    durations = [row.duration_hours for row in rows if row.duration_hours is not None]
    gains = [
        row.health_gain for row in rows if row.health_gain is not None
    ]

    return MaintenanceHistorySummary(
        completed=outcomes.get(MaintenanceOutcome.COMPLETED, 0),
        scheduled=outcomes.get(MaintenanceOutcome.SCHEDULED, 0),
        in_progress=outcomes.get(MaintenanceOutcome.IN_PROGRESS, 0),
        deferred=outcomes.get(MaintenanceOutcome.DEFERRED, 0),
        total_cost=round(sum(row.cost or 0.0 for row in rows), 2),
        mean_duration_hours=(
            round(sum(durations) / len(durations), 2) if durations else None
        ),
        mean_health_gain=round(sum(gains) / len(gains), 2) if gains else None,
    )

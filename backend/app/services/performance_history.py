"""Historical Asset Performance Management and Overall Equipment Efficiency.

Layers 1 to 4 have their history answered by
:mod:`app.services.intelligence_history`. Layers 5 and 6 are kept here rather
than appended to it because they ask a different *kind* of question.

The lower layers are event-shaped: an anomaly happened, a plan was raised, a
recommendation was issued, and history means listing those events within a
window. APM and OEE are state-shaped — every asset has a health index and an
OEE at every instant, and history means the *trajectory* of a continuous
measure. That difference drives everything below: these queries aggregate
across assets and bucket across time, where the event queries filter and list.

Range resolution is still shared with
:func:`app.services.intelligence_history.window_for`, so "last 7 days" means
the same window on every screen in the platform.

Bucketing happens in PostgreSQL. A month of fifteen-second computations is
roughly 170,000 rows per scope; transferring those to Python to average them
would defeat the purpose of aggregating at all, and is exactly the mistake the
telemetry tiering in :mod:`app.services.history_service` exists to avoid.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApmResult, Asset, OeeAssetResult, OeeResult
from app.schemas.enums import AssetType, ScopeType
from app.schemas.intelligence import (
    ApmRead,
    ApmTrendPoint,
    OeeAssetRead,
    OeeRollup,
    OeeTrendPoint,
)

#: Calendar buckets the rollup endpoints accept, mapped to the PostgreSQL
#: ``date_trunc`` field that produces them. Weeks are ISO weeks beginning
#: Monday, which is what ``date_trunc('week', ...)`` returns — stating it here
#: rather than leaving it implicit, because a reporting week that silently
#: starts on Sunday is the kind of discrepancy that surfaces only when somebody
#: reconciles two reports by hand.
ROLLUP_PERIODS: dict[str, str] = {
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
}


def _stamp(payload: dict, asset: Asset) -> dict:
    """Attach asset identity to a result projection.

    Mirrors the helper in :mod:`app.services.intelligence_history`; the two
    modules project different tables through the same asset join.
    """
    payload.update(
        asset_code=asset.asset_code,
        asset_name=asset.name,
        asset_type=asset.asset_type,
    )
    return payload


def _scoped(query: Select, *, asset_type: AssetType | None, asset_id: uuid.UUID | None) -> Select:
    """Apply the two filters every query in this module supports."""
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)
    if asset_id is not None:
        query = query.where(Asset.id == asset_id)
    return query


# --- Layer 5: APM history --------------------------------------------------------


async def apm_history(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_id: uuid.UUID | None = None,
    asset_type: AssetType | None = None,
    limit: int = 500,
) -> list[ApmRead]:
    """Individual APM results within a window, newest first.

    Row-level rather than aggregated, for the case where the question is "what
    did this specific asset look like at 14:00 last Tuesday" rather than "how
    has the fleet moved".
    """
    query = (
        select(ApmResult, Asset)
        .join(Asset, ApmResult.asset_id == Asset.id)
        .where(ApmResult.computed_at >= start, ApmResult.computed_at <= end)
        .order_by(ApmResult.computed_at.desc(), ApmResult.rank)
        .limit(limit)
    )
    query = _scoped(query, asset_type=asset_type, asset_id=asset_id)

    rows = (await session.execute(query)).all()
    return [
        ApmRead(**_stamp(ApmRead.model_validate(result).model_dump(), asset))
        for result, asset in rows
    ]


async def apm_trend(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    asset_id: uuid.UUID | None = None,
    asset_type: AssetType | None = None,
    points: int = 240,
) -> list[ApmTrendPoint]:
    """APM measures over time, averaged across the selected assets.

    One point per computation cycle. When a single asset is selected the
    average is over one row and the series is that asset's own trajectory;
    with no filter it is the fleet's. Both are the same query, which is what
    lets one endpoint serve the fleet chart and the drill-down chart.

    Cost fields are summed rather than averaged: total exposure across a fleet
    is the meaningful figure, where a mean exposure would shrink simply because
    the fleet grew.
    """
    query = (
        select(
            ApmResult.computed_at.label("computed_at"),
            func.avg(ApmResult.health_index).label("health_index"),
            func.avg(ApmResult.availability).label("availability"),
            func.avg(ApmResult.reliability).label("reliability"),
            func.avg(ApmResult.maintainability).label("maintainability"),
            func.avg(ApmResult.utilization).label("utilization"),
            func.avg(ApmResult.lifecycle_score).label("lifecycle_score"),
            func.avg(ApmResult.risk_score).label("risk_score"),
            func.sum(ApmResult.cost_exposure).label("cost_exposure"),
            func.sum(ApmResult.maintenance_cost).label("maintenance_cost"),
            func.sum(ApmResult.energy_cost).label("energy_cost"),
            func.sum(ApmResult.business_value).label("business_value"),
            func.sum(ApmResult.failure_count).label("failure_count"),
            func.count().label("asset_count"),
        )
        .join(Asset, ApmResult.asset_id == Asset.id)
        .where(ApmResult.computed_at >= start, ApmResult.computed_at <= end)
        .group_by(ApmResult.computed_at)
        .order_by(ApmResult.computed_at.desc())
        .limit(points)
    )
    query = _scoped(query, asset_type=asset_type, asset_id=asset_id)

    rows = (await session.execute(query)).all()

    # Descending in SQL so LIMIT keeps the most recent points, reversed here so
    # the series reads left to right for charting.
    return [
        ApmTrendPoint(
            computed_at=row.computed_at,
            health_index=round(float(row.health_index or 0.0), 2),
            availability=round(float(row.availability or 0.0), 4),
            reliability=round(float(row.reliability or 0.0), 4),
            maintainability=round(float(row.maintainability or 0.0), 4),
            utilization=round(float(row.utilization or 0.0), 4),
            lifecycle_score=round(float(row.lifecycle_score or 0.0), 2),
            risk_score=round(float(row.risk_score or 0.0), 4),
            cost_exposure=round(float(row.cost_exposure or 0.0), 2),
            maintenance_cost=round(float(row.maintenance_cost or 0.0), 2),
            energy_cost=round(float(row.energy_cost or 0.0), 4),
            business_value=round(float(row.business_value or 0.0), 2),
            failure_count=int(row.failure_count or 0),
            asset_count=int(row.asset_count or 0),
        )
        for row in reversed(rows)
    ]


# --- Layer 6: OEE history ---------------------------------------------------------


async def oee_asset_latest(
    session: AsyncSession,
    *,
    asset_type: AssetType | None = None,
    limit: int = 500,
) -> list[OeeAssetRead]:
    """Newest per-asset OEE, best first.

    The whole fleet writes one row each per cycle stamped with the same
    ``computed_at``, so selecting that timestamp is what "latest" means.
    """
    latest = await session.scalar(select(func.max(OeeAssetResult.computed_at)))
    if latest is None:
        return []

    query = (
        select(OeeAssetResult, Asset)
        .join(Asset, OeeAssetResult.asset_id == Asset.id)
        .where(OeeAssetResult.computed_at == latest)
        .order_by(OeeAssetResult.rank)
        .limit(limit)
    )
    query = _scoped(query, asset_type=asset_type, asset_id=None)

    rows = (await session.execute(query)).all()
    return [
        OeeAssetRead(**_stamp(OeeAssetRead.model_validate(result).model_dump(), asset))
        for result, asset in rows
    ]


async def oee_for_asset(
    session: AsyncSession, asset_id: uuid.UUID
) -> OeeAssetRead | None:
    """Newest OEE for one asset."""
    row = (
        await session.execute(
            select(OeeAssetResult, Asset)
            .join(Asset, OeeAssetResult.asset_id == Asset.id)
            .where(OeeAssetResult.asset_id == asset_id)
            .order_by(OeeAssetResult.computed_at.desc())
            .limit(1)
        )
    ).first()

    if row is None:
        return None

    result, asset = row
    return OeeAssetRead(
        **_stamp(OeeAssetRead.model_validate(result).model_dump(), asset)
    )


async def oee_asset_trend(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    start: datetime,
    end: datetime,
    points: int = 240,
) -> list[OeeTrendPoint]:
    """One asset's OEE trajectory.

    Reads the per-asset table directly rather than reconstructing the asset's
    contribution from a rollup, which cannot be done: an average has already
    discarded the individual terms that produced it.
    """
    rows = (
        await session.scalars(
            select(OeeAssetResult)
            .where(
                OeeAssetResult.asset_id == asset_id,
                OeeAssetResult.computed_at >= start,
                OeeAssetResult.computed_at <= end,
            )
            .order_by(OeeAssetResult.computed_at.desc())
            .limit(points)
        )
    ).all()

    return [
        OeeTrendPoint(
            computed_at=row.computed_at,
            availability=row.availability,
            performance=row.performance,
            quality=row.quality,
            oee=row.oee,
            asset_count=1,
        )
        for row in reversed(rows)
    ]


async def oee_scope_trend(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    scope: ScopeType = ScopeType.ENTERPRISE,
    scope_label: str | None = None,
    asset_type: AssetType | None = None,
    points: int = 240,
) -> list[OeeTrendPoint]:
    """OEE trajectory at an aggregation scope.

    ``scope_label`` selects one entity within a scope — a single building, say
    — while omitting it averages every entity at that level. ``asset_type``
    narrows to the per-category rollups.
    """
    query = (
        select(
            OeeResult.computed_at.label("computed_at"),
            func.avg(OeeResult.availability).label("availability"),
            func.avg(OeeResult.performance).label("performance"),
            func.avg(OeeResult.quality).label("quality"),
            func.avg(OeeResult.oee).label("oee"),
            func.sum(OeeResult.asset_count).label("asset_count"),
        )
        .where(
            OeeResult.scope_type == scope,
            OeeResult.computed_at >= start,
            OeeResult.computed_at <= end,
        )
        .group_by(OeeResult.computed_at)
        .order_by(OeeResult.computed_at.desc())
        .limit(points)
    )

    if scope_label is not None:
        query = query.where(OeeResult.scope_label == scope_label)
    if asset_type is not None:
        query = query.where(OeeResult.asset_type == asset_type)

    rows = (await session.execute(query)).all()

    return [
        OeeTrendPoint(
            computed_at=row.computed_at,
            availability=round(float(row.availability or 0.0), 4),
            performance=round(float(row.performance or 0.0), 4),
            quality=round(float(row.quality or 0.0), 4),
            oee=round(float(row.oee or 0.0), 4),
            asset_count=int(row.asset_count or 0),
        )
        for row in reversed(rows)
    ]


async def oee_rollup(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    period: str = "daily",
    scope: ScopeType = ScopeType.ENTERPRISE,
    asset_type: AssetType | None = None,
) -> list[OeeRollup]:
    """OEE averaged into calendar buckets.

    The daily, weekly and monthly views the SSOT asks for. Bucketing runs in
    PostgreSQL via ``date_trunc``; a month of fifteen-second computations is
    around 170,000 rows, and averaging those client-side would transfer two
    orders of magnitude more data than the chart draws.

    ``samples`` is returned so a partial bucket is visibly partial. A month-to-
    date bar carrying three days of data should not silently sit beside twelve
    complete months as though it were their equal.
    """
    field = ROLLUP_PERIODS.get(period)
    if field is None:
        raise ValueError(
            f"Unsupported rollup period {period!r}; "
            f"expected one of {', '.join(sorted(ROLLUP_PERIODS))}."
        )

    bucket = func.date_trunc(field, OeeResult.computed_at).label("bucket")

    query = (
        select(
            bucket,
            func.avg(OeeResult.availability).label("availability"),
            func.avg(OeeResult.performance).label("performance"),
            func.avg(OeeResult.quality).label("quality"),
            func.avg(OeeResult.oee).label("oee"),
            func.count().label("samples"),
        )
        .where(
            OeeResult.scope_type == scope,
            OeeResult.computed_at >= start,
            OeeResult.computed_at <= end,
        )
        .group_by(bucket)
        .order_by(bucket)
    )

    if asset_type is not None:
        query = query.where(OeeResult.asset_type == asset_type)

    rows = (await session.execute(query)).all()

    return [
        OeeRollup(
            bucket=row.bucket,
            period=period,
            availability=round(float(row.availability or 0.0), 4),
            performance=round(float(row.performance or 0.0), 4),
            quality=round(float(row.quality or 0.0), 4),
            oee=round(float(row.oee or 0.0), 4),
            samples=int(row.samples or 0),
        )
        for row in rows
    ]

"""Telemetry endpoints.

Reads come from the hypertable with a mandatory window; the live snapshot comes
from memory. Writes go through the same pipeline the Digital Twin uses — there
is exactly one way into the Telemetry Layer.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.errors import NotFoundError
from app.models import Asset, Telemetry
from app.routers.deps import PaginationDep, SessionDep, WindowDep
from app.schemas.common import Envelope, Page, PageMeta, envelope
from app.schemas.dashboard import RecentTelemetryRow
from app.schemas.enums import AssetType, TimeRange
from app.schemas.telemetry import ChartSeries, TelemetryIngest
from app.services.history_service import (
    fetch_series_resilient,
    resolve_range,
    resolve_window,
    select_tier,
)
from app.services.live_state import live_state
from app.services.telemetry_service import telemetry_service

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.get(
    "",
    response_model=Envelope[Page[RecentTelemetryRow]],
    summary="Query telemetry",
    description="Paginated readings within an explicit window. Retention is "
    "unlimited, so a window is always required — it defaults to the last hour.",
)
async def query_telemetry(
    session: SessionDep,
    pagination: PaginationDep,
    window: WindowDep,
    asset_id: Annotated[uuid.UUID | None, Query()] = None,
    asset_type: Annotated[AssetType | None, Query()] = None,
) -> Envelope[Page[RecentTelemetryRow]]:
    """Readings in a window, newest first."""
    query = (
        select(Telemetry, Asset)
        .join(Asset, Telemetry.asset_id == Asset.id)
        .where(Telemetry.time >= window.start, Telemetry.time <= window.end)
    )
    count_query = (
        select(func.count())
        .select_from(Telemetry)
        .join(Asset, Telemetry.asset_id == Asset.id)
        .where(Telemetry.time >= window.start, Telemetry.time <= window.end)
    )

    if asset_id is not None:
        query = query.where(Telemetry.asset_id == asset_id)
        count_query = count_query.where(Telemetry.asset_id == asset_id)
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)
        count_query = count_query.where(Asset.asset_type == asset_type)

    total = int(await session.scalar(count_query) or 0)
    rows = (
        await session.execute(
            query.order_by(Telemetry.time.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).all()

    return envelope(
        Page[RecentTelemetryRow](
            items=[
                RecentTelemetryRow(
                    time=telemetry.time,
                    asset_id=asset.id,
                    asset_code=asset.asset_code,
                    asset_name=asset.name,
                    asset_type=asset.asset_type,
                    voltage_v=telemetry.voltage_v,
                    current_a=telemetry.current_a,
                    power_w=telemetry.power_w,
                    energy_kwh=telemetry.energy_kwh,
                    temperature_c=telemetry.temperature_c,
                    frequency_hz=telemetry.frequency_hz,
                    power_factor=telemetry.power_factor,
                    health_score=telemetry.health_score,
                    health_state=telemetry.health_state,
                    quality=str(telemetry.quality),
                )
                for telemetry, asset in rows
            ],
            meta=PageMeta.build(
                page=pagination.page, page_size=pagination.page_size, total_items=total
            ),
        )
    )


@router.get(
    "/live",
    response_model=Envelope[list[TelemetryIngest]],
    summary="Current snapshot",
    description="Newest reading per asset, served from memory. The WebSocket at "
    "/ws/live is the preferred channel; this exists for clients that cannot "
    "hold a socket open.",
)
async def get_live(
    asset_type: Annotated[AssetType | None, Query()] = None,
) -> Envelope[list[TelemetryIngest]]:
    """The live snapshot, without touching the hypertable."""
    readings = list(live_state.all_latest().values())

    if asset_type is not None:
        readings = [
            reading
            for reading in readings
            if (identity := live_state.identity(reading.asset_id)) is not None
            and identity.asset_type is asset_type
        ]

    return envelope(readings)


@router.get(
    "/history",
    response_model=Envelope[list[ChartSeries]],
    summary="Downsampled history",
    description="Time-bucketed series for charting. Supply either a named "
    "`range` (live, last_hour, today, last_7_days, last_30_days) or explicit "
    "bounds. The window determines which storage tier answers the query — raw "
    "telemetry for short ranges, one-minute or one-hour rollups for long ones "
    "— so a thirty-day chart costs thousands of rows rather than hundreds of "
    "millions.",
)
async def get_history(
    session: SessionDep,
    window: WindowDep,
    time_range: Annotated[
        TimeRange | None,
        Query(alias="range", description="Named window. Overrides minutes."),
    ] = None,
    asset_id: Annotated[uuid.UUID | None, Query()] = None,
    asset_type: Annotated[AssetType | None, Query()] = None,
    channels: Annotated[
        str, Query(description="Comma-separated channel keys.")
    ] = "power_w,temperature_c,health_score",
    points: Annotated[int, Query(ge=10, le=1000)] = 180,
) -> Envelope[list[ChartSeries]]:
    """Return one downsampled series per requested channel.

    Bucketing happens in the database. Transferring a million rows to average
    them in the application would defeat the point of a time-series store.
    """
    resolved = (
        resolve_window(time_range=time_range)
        if time_range is not None
        else resolve_window(start=window.start, end=window.end)
    )

    series, served_by = await fetch_series_resilient(
        session,
        window=resolved,
        channels=[channel.strip() for channel in channels.split(",")],
        asset_id=asset_id,
        asset_type=asset_type,
        points=points,
    )

    return envelope(
        series,
        message=f"Resolved from {served_by.resolution} resolution.",
    )


@router.get(
    "/ranges",
    response_model=Envelope[list[dict[str, object]]],
    summary="Supported history ranges",
    description="The named windows the platform can answer, and which storage "
    "tier serves each. Exposed so clients can present ranges without "
    "hardcoding the platform's retention strategy.",
)
async def get_ranges() -> Envelope[list[dict[str, object]]]:
    """Describe every named range and the tier that answers it."""
    described: list[dict[str, object]] = []

    for value in TimeRange:
        start, end = resolve_range(value)
        resolved = select_tier(start, end)
        described.append(
            {
                "range": value.value,
                "label": value.value.replace("_", " ").title(),
                "start": start,
                "end": end,
                "hours": round((end - start).total_seconds() / 3600.0, 2),
                "resolution": resolved.resolution,
                "source": resolved.source,
            }
        )

    return envelope(described)


@router.post(
    "",
    response_model=Envelope[dict[str, int]],
    summary="Ingest telemetry",
    description="External ingestion path. Readings follow exactly the same "
    "validate, normalise, store and broadcast pipeline as the Digital Twin.",
)
async def ingest(
    readings: list[TelemetryIngest], session: SessionDep
) -> Envelope[dict[str, int]]:
    """Accept readings from an external source."""
    known = {identity.id for identity in live_state.identities()}
    unknown = {reading.asset_id for reading in readings} - known
    if unknown:
        missing = await session.scalars(select(Asset.id).where(Asset.id.in_(unknown)))
        still_unknown = unknown - set(missing.all())
        if still_unknown:
            raise NotFoundError(
                f"{len(still_unknown)} reading(s) reference assets that do not exist."
            )

    accepted = await telemetry_service.ingest_batch(readings)
    return envelope(
        {"received": len(readings), "accepted": accepted},
        message=f"{accepted} reading(s) ingested.",
    )

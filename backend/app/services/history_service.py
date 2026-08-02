"""Historical telemetry queries.

Answers "show me the last thirty days" without scanning thirty days of
one-second rows. Each request is routed to the cheapest storage tier that can
answer it accurately, and re-bucketed to roughly the number of points the
caller can actually plot.

The tier is chosen from the window, not from the caller's preference. A client
asking for a month of data does not want three hundred million rows even if it
thinks it does — it wants a few hundred points that faithfully describe a
month, and that is what a rollup is for.

Downsampling happens in the database. Transferring rows to Python to average
them would defeat the entire purpose of a time-series store.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.timescale import HOUR_VIEW, MINUTE_VIEW
from app.schemas.enums import AssetType, TimeRange
from app.schemas.telemetry import ChartSeries, SeriesPoint
from app.utils.time import start_of_utc_day, utc_now

#: Channels a history query may request, with display label and unit.
HISTORY_CHANNELS: dict[str, tuple[str, str]] = {
    "voltage_v": ("Voltage", "V"),
    "current_a": ("Current", "A"),
    "power_w": ("Power", "W"),
    "reactive_power_var": ("Reactive Power", "VAr"),
    "apparent_power_va": ("Apparent Power", "VA"),
    "energy_kwh": ("Energy", "kWh"),
    "temperature_c": ("Temperature", "°C"),
    "indoor_temperature_c": ("Indoor Temperature", "°C"),
    "frequency_hz": ("Frequency", "Hz"),
    "power_factor": ("Power Factor", ""),
    "health_score": ("Health", "%"),
    "load_percent": ("Load", "%"),
    "battery_percent": ("Battery", "%"),
}

#: Channels that are cumulative meters. Averaging a lifetime counter is
#: meaningless; the maximum within a bucket is the reading at its end.
_CUMULATIVE = frozenset({"energy_kwh", "runtime_hours", "charge_cycles"})

#: Window above which the one-minute rollup replaces raw rows.
_RAW_LIMIT = timedelta(hours=6)

#: Window above which the one-hour rollup replaces the one-minute one.
_MINUTE_LIMIT = timedelta(days=3)


@dataclass(frozen=True, slots=True)
class ResolvedWindow:
    """A concrete time window and the tier that will answer it."""

    start: datetime
    end: datetime
    #: Relation the query reads from.
    source: str
    #: Timestamp column on that relation.
    time_column: str
    #: Human-readable tier name, returned to the caller for transparency.
    resolution: str

    @property
    def seconds(self) -> float:
        return max((self.end - self.start).total_seconds(), 1.0)


def resolve_range(
    time_range: TimeRange, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """Turn a named range into explicit bounds.

    ``TODAY`` is anchored to midnight UTC rather than "the last 24 hours" —
    those are different questions, and an energy figure labelled "today" that
    silently means "since this time yesterday" is wrong in a way nobody
    notices until it is reconciled against a bill.
    """
    reference = now or utc_now()

    match time_range:
        case TimeRange.LIVE:
            return reference - timedelta(minutes=15), reference
        case TimeRange.LAST_HOUR:
            return reference - timedelta(hours=1), reference
        case TimeRange.TODAY:
            return start_of_utc_day(reference), reference
        case TimeRange.LAST_7_DAYS:
            return reference - timedelta(days=7), reference
        case TimeRange.LAST_30_DAYS:
            return reference - timedelta(days=30), reference

    return reference - timedelta(hours=1), reference


def select_tier(start: datetime, end: datetime) -> ResolvedWindow:
    """Choose the storage tier that can answer this window most cheaply."""
    span = end - start

    if span <= _RAW_LIMIT:
        return ResolvedWindow(start, end, "telemetry", "time", "raw")
    if span <= _MINUTE_LIMIT:
        return ResolvedWindow(start, end, MINUTE_VIEW, "bucket", "1 minute")
    return ResolvedWindow(start, end, HOUR_VIEW, "bucket", "1 hour")


def finer_tier(window: ResolvedWindow) -> ResolvedWindow | None:
    """The next more granular tier for the same window, if one exists."""
    if window.source == HOUR_VIEW:
        return ResolvedWindow(
            window.start, window.end, MINUTE_VIEW, "bucket", "1 minute"
        )
    if window.source == MINUTE_VIEW:
        return ResolvedWindow(window.start, window.end, "telemetry", "time", "raw")
    return None


#: Rows a fallback query may scan. Generous enough to cover a young deployment
#: whose rollups have not materialised, small enough that it can never turn
#: into a full scan of a mature hypertable.
FALLBACK_ROW_BUDGET = 1_500_000


def resolve_window(
    *,
    time_range: TimeRange | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    minutes: int | None = None,
) -> ResolvedWindow:
    """Resolve a window from whichever form the caller supplied."""
    if start is not None and end is not None:
        bounds = (start, end) if start <= end else (end, start)
    elif time_range is not None:
        bounds = resolve_range(time_range)
    else:
        reference = utc_now()
        bounds = (reference - timedelta(minutes=minutes or 60), reference)

    return select_tier(*bounds)


async def fetch_series(
    session: AsyncSession,
    *,
    window: ResolvedWindow,
    channels: list[str],
    asset_id: uuid.UUID | None = None,
    asset_type: AssetType | None = None,
    points: int = 240,
) -> list[ChartSeries]:
    """Fetch downsampled series for the requested channels.

    Buckets are sized so the result lands near ``points`` regardless of window
    length, and never finer than the underlying tier — asking for a thousand
    points from an hourly rollup over a week cannot manufacture resolution that
    was never stored.
    """
    requested = [channel for channel in channels if channel in HISTORY_CHANNELS]
    if not requested:
        requested = ["power_w"]

    bucket_seconds = max(1.0, window.seconds / max(points, 2))

    # Floor each timestamp onto a bucket boundary. Expressed in plain SQL so
    # the same query works against the raw hypertable and both rollups, and on
    # plain PostgreSQL without TimescaleDB.
    time_col = f"t.{window.time_column}"
    bucket_expr = (
        f"to_timestamp(floor(extract(epoch FROM {time_col}) / {bucket_seconds})"
        f" * {bucket_seconds})"
    )

    projections = ", ".join(
        f"{'max' if channel in _CUMULATIVE else 'avg'}(t.{channel}) AS {channel}"
        for channel in requested
    )

    filters = [f"{time_col} >= :start", f"{time_col} <= :end"]
    params: dict[str, object] = {"start": window.start, "end": window.end}

    if asset_id is not None:
        filters.append("t.asset_id = :asset_id")
        params["asset_id"] = asset_id

    join = ""
    if asset_type is not None:
        join = "JOIN assets a ON a.id = t.asset_id"
        filters.append("a.asset_type = :asset_type")
        params["asset_type"] = asset_type.value

    statement = text(
        f"""
        SELECT {bucket_expr} AS bucket, {projections}
        FROM {window.source} t
        {join}
        WHERE {' AND '.join(filters)}
        GROUP BY bucket
        ORDER BY bucket
        """
    )

    rows = (await session.execute(statement, params)).all()

    series: list[ChartSeries] = []
    for index, channel in enumerate(requested):
        label, unit = HISTORY_CHANNELS[channel]
        series.append(
            ChartSeries(
                key=channel,
                label=label,
                unit=unit,
                points=[
                    SeriesPoint(
                        t=row[0],
                        v=None if row[index + 1] is None else round(float(row[index + 1]), 4),
                    )
                    for row in rows
                ],
            )
        )

    return series


async def fetch_series_resilient(
    session: AsyncSession,
    *,
    window: ResolvedWindow,
    channels: list[str],
    asset_id: uuid.UUID | None = None,
    asset_type: AssetType | None = None,
    points: int = 240,
) -> tuple[list[ChartSeries], ResolvedWindow]:
    """Fetch series, stepping down a tier if the chosen one is still empty.

    A continuous aggregate only materialises buckets old enough to be complete
    — the hourly rollup ignores anything from the last hour. On a deployment
    that started ten minutes ago the correct tier for "last 7 days" therefore
    holds nothing at all, and the user sees an empty chart while the raw table
    is filling up in front of them.

    So an empty result falls through to the next finer tier, but only after
    checking how many rows that would actually scan. The budget is what keeps
    this from silently becoming a full hypertable scan once the deployment is
    mature and the rollups are genuinely the right answer.

    Returns the series along with the tier that produced them, so the caller
    can tell the user what they are looking at.
    """
    current: ResolvedWindow | None = window

    while current is not None:
        series = await fetch_series(
            session,
            window=current,
            channels=channels,
            asset_id=asset_id,
            asset_type=asset_type,
            points=points,
        )
        if any(entry.points for entry in series):
            return series, current

        candidate = finer_tier(current)
        if candidate is None:
            return series, current

        if await count_rows(session, window=candidate) > FALLBACK_ROW_BUDGET:
            # The finer tier holds plenty of data; the rollup being empty is
            # not a cold-start artefact, so stop rather than scan it.
            return series, current

        current = candidate

    return [], window


async def fetch_energy_totals(
    session: AsyncSession,
    *,
    window: ResolvedWindow,
    asset_type: AssetType | None = None,
) -> dict[str, float]:
    """Energy consumed within a window, across metered assets.

    Meters are cumulative, so consumption is the difference between the last
    and first reading per asset — not a sum of readings, which would be a
    meaningless total of running totals.
    """
    time_col = f"t.{window.time_column}"
    filters = [f"{time_col} >= :start", f"{time_col} <= :end", "t.energy_kwh IS NOT NULL"]
    params: dict[str, object] = {"start": window.start, "end": window.end}

    join = ""
    if asset_type is not None:
        join = "JOIN assets a ON a.id = t.asset_id"
        filters.append("a.asset_type = :asset_type")
        params["asset_type"] = asset_type.value

    statement = text(
        f"""
        SELECT
            coalesce(sum(span.delta), 0)  AS total_kwh,
            count(*)                      AS metered_assets
        FROM (
            SELECT t.asset_id,
                   max(t.energy_kwh) - min(t.energy_kwh) AS delta
            FROM {window.source} t
            {join}
            WHERE {' AND '.join(filters)}
            GROUP BY t.asset_id
        ) span
        """
    )

    row = (await session.execute(statement, params)).one()
    return {"total_kwh": float(row[0] or 0.0), "metered_assets": int(row[1] or 0)}


async def count_rows(session: AsyncSession, *, window: ResolvedWindow) -> int:
    """Row count in the tier answering this window, for diagnostics."""
    statement = text(
        f"SELECT count(*) FROM {window.source} t "
        f"WHERE t.{window.time_column} >= :start AND t.{window.time_column} <= :end"
    )
    result = await session.execute(statement, {"start": window.start, "end": window.end})
    return int(result.scalar() or 0)


# Retained so callers can build ORM-level queries against the raw table without
# reaching for the text() form above.
def raw_time_filter(start: datetime, end: datetime):
    """SQLAlchemy predicate restricting the raw hypertable to a window."""
    from app.models import Telemetry

    return (Telemetry.time >= start, Telemetry.time <= end)


__all__ = [
    "FALLBACK_ROW_BUDGET",
    "HISTORY_CHANNELS",
    "ResolvedWindow",
    "count_rows",
    "fetch_energy_totals",
    "fetch_series",
    "fetch_series_resilient",
    "finer_tier",
    "raw_time_filter",
    "resolve_range",
    "resolve_window",
    "select_tier",
]

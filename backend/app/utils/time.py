"""Time helpers.

INTELORA is timezone-aware end to end and stores everything in UTC. Naive
datetimes are a source of silent, hard-to-trace errors in a platform that
reports "today's energy" across organisations in different regions, so they are
never allowed past this module.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


def utc_now() -> datetime:
    """Current instant, timezone-aware, in UTC."""
    return datetime.now(tz=timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """Return ``value`` as a UTC-aware datetime.

    A naive input is interpreted as already being UTC, which matches how the
    database returns values when a column was written without a zone.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def start_of_utc_day(moment: datetime | None = None) -> datetime:
    """Midnight UTC of the day containing ``moment``.

    This is the boundary behind every "today's ..." figure on the Cockpit.
    """
    reference = ensure_utc(moment or utc_now())
    return datetime.combine(reference.date(), time.min, tzinfo=timezone.utc)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Half-open ``[start, end)`` UTC bounds for a calendar day."""
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def minutes_ago(minutes: float, *, reference: datetime | None = None) -> datetime:
    """Instant ``minutes`` before ``reference`` (default: now)."""
    return ensure_utc(reference or utc_now()) - timedelta(minutes=minutes)


def hours_between(earlier: datetime, later: datetime) -> float:
    """Elapsed hours between two instants, never negative."""
    delta = ensure_utc(later) - ensure_utc(earlier)
    return max(delta.total_seconds() / 3600.0, 0.0)

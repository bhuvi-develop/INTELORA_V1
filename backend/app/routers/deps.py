"""Shared router dependencies.

Common query parameters are declared once here so that pagination and time
windows behave identically on every collection endpoint. Retention is
unlimited, so an unbounded request is never the default.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.utils.time import minutes_ago, utc_now

#: Request-scoped database session.
SessionDep = Annotated[AsyncSession, Depends(get_session)]


class Pagination(BaseModel):
    """Offset pagination, bounded so a client cannot request the whole table."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: Annotated[int, Query(ge=1, description="1-indexed page number.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=200, description="Rows per page, capped at 200.")
    ] = 25,
) -> Pagination:
    """Standard pagination for every collection endpoint."""
    return Pagination(page=page, page_size=page_size)


PaginationDep = Annotated[Pagination, Depends(pagination_params)]


class Window(BaseModel):
    """A closed time range."""

    start: datetime
    end: datetime

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0


def window_params(
    minutes: Annotated[
        int,
        Query(
            ge=1,
            le=525_600,
            description="Length of the window ending now, in minutes. "
            "Ignored when explicit start and end are supplied.",
        ),
    ] = 60,
    start: Annotated[datetime | None, Query(description="Explicit window start.")] = None,
    end: Annotated[datetime | None, Query(description="Explicit window end.")] = None,
) -> Window:
    """Resolve a time window from either a duration or explicit bounds.

    Defaults to the last hour rather than to all history: the difference
    between those two against a hypertable is unbounded.
    """
    resolved_end = end or utc_now()
    resolved_start = start or minutes_ago(minutes, reference=resolved_end)
    if resolved_start > resolved_end:
        resolved_start, resolved_end = resolved_end, resolved_start
    return Window(start=resolved_start, end=resolved_end)


WindowDep = Annotated[Window, Depends(window_params)]

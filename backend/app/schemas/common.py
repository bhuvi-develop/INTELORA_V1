"""Shared response shapes.

Every INTELORA endpoint answers with the same envelope. ``status`` is a boolean
inside the body, independent of the HTTP status code, so clients must unwrap
the envelope rather than trusting the transport alone.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.utils.time import utc_now

DataT = TypeVar("DataT")


class ApiError(BaseModel):
    """A single machine-readable failure.

    ``code`` is stable across releases; the frontend maps it to localised copy
    rather than displaying ``message`` verbatim.
    """

    model_config = ConfigDict(use_enum_values=True)

    code: str
    message: str
    field: str | None = None


class Envelope(BaseModel, Generic[DataT]):
    """The uniform response body."""

    status: bool = True
    message: str = "Success"
    timestamp: datetime = Field(default_factory=utc_now)
    data: DataT | None = None
    errors: list[ApiError] = Field(default_factory=list)


def envelope(
    data: DataT | None = None,
    *,
    message: str = "Success",
    errors: list[ApiError] | None = None,
    ok: bool = True,
) -> Envelope[DataT]:
    """Build a response envelope.

    Routers return this rather than bare payloads, which keeps the contract in
    one place instead of repeated at every call site.
    """
    return Envelope[DataT](
        status=ok,
        message=message,
        timestamp=utc_now(),
        data=data,
        errors=errors or [],
    )


class PageMeta(BaseModel):
    """Pagination metadata.

    Telemetry retention is unlimited, so every collection endpoint is paginated
    and no client may assume it has received a complete set.
    """

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)

    @classmethod
    def build(cls, *, page: int, page_size: int, total_items: int) -> PageMeta:
        total_pages = (total_items + page_size - 1) // page_size if page_size else 0
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )


class Page(BaseModel, Generic[DataT]):
    """A single page of a collection."""

    items: list[DataT]
    meta: PageMeta


class TimeRange(BaseModel):
    """An explicit, closed time window.

    Required wherever history is queried — an unbounded range against an
    unlimited-retention hypertable is never acceptable.
    """

    start: datetime
    end: datetime


class HealthCheck(BaseModel):
    """Liveness payload for orchestrators and the container healthcheck."""

    status: str
    version: str
    environment: str
    database_connected: bool
    twin_running: bool
    timestamp: datetime = Field(default_factory=utc_now)

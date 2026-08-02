"""Maintenance history.

The `maintenance_logs` table has been in the data architecture since the SSOT
was written and was never built. Without it the platform can predict and
schedule maintenance but has no record that any was ever done — which breaks
more than the history page:

* Preventive scheduling falls back to the commissioning date, so every asset
  reads as "never serviced" forever. That is why the platform currently reports
  92 of 120 assets overdue.
* MTTR is unmeasurable, because nothing records how long a repair took.
* Maintenance ROI is guesswork, because actual cost is never captured.

Entries are created by the platform when a plan is generated, and completed by
an operator. The record is append-and-update, never deleted: an asset's service
history is exactly the kind of thing an auditor asks for.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import enum_column
from app.schemas.enums import (
    MaintenanceOutcome,
    MaintenanceTaskType,
    RiskLevel,
)


class MaintenanceLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One maintenance activity, planned or performed."""

    __tablename__ = "maintenance_logs"
    __table_args__ = (
        Index("ix_maintenance_asset_scheduled", "asset_id", "scheduled_for"),
        Index("ix_maintenance_outcome", "outcome", "scheduled_for"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: The plan that produced this entry, when the platform generated it.
    preventive_result_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("preventive_results.id", ondelete="SET NULL"),
    )

    task_type: Mapped[MaintenanceTaskType] = mapped_column(
        enum_column(MaintenanceTaskType), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[RiskLevel] = mapped_column(
        enum_column(RiskLevel), nullable=False, default=RiskLevel.LOW
    )

    outcome: Mapped[MaintenanceOutcome] = mapped_column(
        enum_column(MaintenanceOutcome),
        nullable=False,
        default=MaintenanceOutcome.SCHEDULED,
        index=True,
    )

    # --- Timing ---------------------------------------------------------------
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    #: Wall-clock hours from start to completion. This is the raw material for
    #: MTTR, which is why it is recorded rather than inferred later.
    duration_hours: Mapped[float | None] = mapped_column(Float)

    # --- Work and outcome ------------------------------------------------------
    checklist: Mapped[list | None] = mapped_column(JSON)
    performed_by: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    cost: Mapped[float | None] = mapped_column(Float)

    #: Asset health immediately before and after, so the value of the work is
    #: measurable rather than assumed.
    health_before: Mapped[float | None] = mapped_column(Float)
    health_after: Mapped[float | None] = mapped_column(Float)

    @property
    def health_gain(self) -> float | None:
        """Health points recovered, when both readings are present."""
        if self.health_before is None or self.health_after is None:
            return None
        return round(self.health_after - self.health_before, 2)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<MaintenanceLog {self.task_type}/{self.outcome} {self.title!r}>"

"""Alerts.

Severity and lifecycle are independent columns: an alert can legitimately be
critical *and* acknowledged, and folding the two into one field would make that
unrepresentable.

``anomaly_result_id`` implements the SSOT integrity chain — every alert
references the AI result that raised it, which in turn references the telemetry
window that triggered it. That chain is what makes alert-to-evidence
drill-through possible in the UI.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import enum_column
from app.schemas.enums import AlertSeverity, AlertStatus, FaultType

if TYPE_CHECKING:
    from app.models.asset import Asset


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An operator-facing event raised by the Anomaly Detection layer."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_asset_triggered", "asset_id", "triggered_at"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    anomaly_result_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("anomaly_results.id", ondelete="SET NULL"),
        index=True,
    )

    severity: Mapped[AlertSeverity] = mapped_column(
        enum_column(AlertSeverity), nullable=False, index=True
    )
    status: Mapped[AlertStatus] = mapped_column(
        enum_column(AlertStatus), nullable=False, default=AlertStatus.ACTIVE, index=True
    )
    fault_type: Mapped[FaultType | None] = mapped_column(enum_column(FaultType), index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # The reading that breached, and the band it was expected to stay within.
    # Carried on the alert so the UI can show the evidence without a join.
    observed_value: Mapped[float | None] = mapped_column(Float)
    expected_min: Mapped[float | None] = mapped_column(Float)
    expected_max: Mapped[float | None] = mapped_column(Float)
    channel: Mapped[str | None] = mapped_column(String(48))

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[str | None] = mapped_column(String(160))

    asset: Mapped[Asset] = relationship(back_populates="alerts")

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<Alert {self.severity}/{self.status} {self.title!r}>"

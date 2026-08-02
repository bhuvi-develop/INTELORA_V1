"""Alert schemas.

Severity and lifecycle are separate fields throughout, never merged into a
single "state" — the two are orthogonal and both are needed to filter a real
operations queue.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AlertSeverity, AlertStatus, AssetType, FaultType


class AlertRead(BaseModel):
    """An alert as presented to an operator."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    asset_code: str | None = None
    asset_name: str | None = None
    asset_type: AssetType | None = None

    severity: AlertSeverity
    status: AlertStatus
    fault_type: FaultType | None = None

    title: str
    message: str

    # Evidence, denormalised onto the alert so the list view can show why it
    # fired without a second round trip.
    channel: str | None = None
    observed_value: float | None = None
    expected_min: float | None = None
    expected_max: float | None = None
    anomaly_result_id: uuid.UUID | None = None

    triggered_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    assigned_to: str | None = None


class AlertUpdate(BaseModel):
    """Lifecycle transition or assignment.

    Severity is intentionally absent: it is determined by the Anomaly Detection
    layer from evidence, and must not be editable by hand.
    """

    status: AlertStatus | None = None
    assigned_to: str | None = Field(default=None, max_length=160)


class AlertSummary(BaseModel):
    """Counts backing the Cockpit alerts section and the navbar badge."""

    total: int = 0
    active: int = 0
    acknowledged: int = 0
    resolved: int = 0
    critical: int = 0
    warning: int = 0
    information: int = 0
    recent: list[AlertRead] = Field(default_factory=list)

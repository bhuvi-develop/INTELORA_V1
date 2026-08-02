"""Pydantic schemas — the API's public contract.

Mirrored by ``frontend/src/types``. Changing a schema here without updating the
corresponding TypeScript declaration will compile on both sides and fail at
runtime, so the two must be edited together.
"""

from app.schemas.alert import AlertRead, AlertSummary, AlertUpdate
from app.schemas.asset import (
    AssetBusinessModel,
    AssetCapabilities,
    AssetCreate,
    AssetRead,
    AssetScope,
    AssetTypeSummary,
    AssetUpdate,
)
from app.schemas.common import (
    ApiError,
    Envelope,
    HealthCheck,
    Page,
    PageMeta,
    TimeRange,
    envelope,
)
from app.schemas.dashboard import (
    ActivityItem,
    ChartBundle,
    CockpitOverview,
    DistributionSlice,
    EnergySummary,
    KpiValue,
    LiveTick,
    RecentTelemetryRow,
    SystemStatus,
)
from app.schemas.intelligence import (
    AnomalyRead,
    AnomalySummary,
    ApmRead,
    ApmSummary,
    IntelligenceSummary,
    OeeRead,
    OeeSummary,
    PredictiveRead,
    PredictiveSummary,
    PrescriptiveRead,
    PrescriptiveSummary,
    PreventiveRead,
    PreventiveSummary,
)
from app.schemas.telemetry import (
    ChartSeries,
    SeriesPoint,
    TelemetryIngest,
    TelemetryQuery,
    TelemetryRead,
)

__all__ = [
    "ActivityItem",
    "AlertRead",
    "AlertSummary",
    "AlertUpdate",
    "AnomalyRead",
    "AnomalySummary",
    "ApiError",
    "ApmRead",
    "ApmSummary",
    "AssetBusinessModel",
    "AssetCapabilities",
    "AssetCreate",
    "AssetRead",
    "AssetScope",
    "AssetTypeSummary",
    "AssetUpdate",
    "ChartBundle",
    "ChartSeries",
    "CockpitOverview",
    "DistributionSlice",
    "EnergySummary",
    "Envelope",
    "HealthCheck",
    "IntelligenceSummary",
    "KpiValue",
    "LiveTick",
    "OeeRead",
    "OeeSummary",
    "Page",
    "PageMeta",
    "PredictiveRead",
    "PredictiveSummary",
    "PrescriptiveRead",
    "PrescriptiveSummary",
    "PreventiveRead",
    "PreventiveSummary",
    "RecentTelemetryRow",
    "SeriesPoint",
    "SystemStatus",
    "TelemetryIngest",
    "TelemetryQuery",
    "TelemetryRead",
    "TimeRange",
    "envelope",
]

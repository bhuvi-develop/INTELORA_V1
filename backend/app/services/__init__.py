"""Service layer.

Everything between the API surface and the database. Routers stay thin and
delegate here, so business logic is testable without a request and reusable
between HTTP handlers and background tasks.
"""

from app.services.business_model import (
    build_all_business_models,
    build_business_model,
    energy_ledger,
    summarise_asset_types,
)
from app.services.dashboard_service import (
    activity_log,
    build_chart_bundle,
    build_cockpit_overview,
    build_live_tick,
    reset_dashboard_state,
)
from app.services.health_engine import (
    HealthAssessment,
    HealthEngine,
    health_engine,
    health_state_for,
)
from app.services.history_service import (
    fetch_series,
    resolve_range,
    resolve_window,
    select_tier,
)
from app.services.live_state import AssetIdentity, LiveState, live_state
from app.services.telemetry_service import TelemetryService, telemetry_service

__all__ = [
    "AssetIdentity",
    "HealthAssessment",
    "HealthEngine",
    "LiveState",
    "TelemetryService",
    "activity_log",
    "build_all_business_models",
    "build_business_model",
    "build_chart_bundle",
    "build_cockpit_overview",
    "build_live_tick",
    "energy_ledger",
    "fetch_series",
    "health_engine",
    "health_state_for",
    "live_state",
    "reset_dashboard_state",
    "resolve_range",
    "resolve_window",
    "select_tier",
    "summarise_asset_types",
    "telemetry_service",
]

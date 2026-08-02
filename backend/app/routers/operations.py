"""Operational endpoints: Digital Twin control, reports, settings and health.

Grouped together because all four are platform administration rather than
domain data, and each is small enough that a file apiece would be structure for
its own sake.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import settings as app_settings
from app.core.errors import InvalidStateError, NotFoundError
from app.database.session import engine
from app.database.timescale import rollup_health
from app.intelligence.runner import intelligence_runner
from app.models import Asset, SystemSetting, Telemetry
from app.routers.deps import SessionDep, WindowDep
from app.schemas.common import Envelope, HealthCheck, envelope
from app.schemas.enums import TwinScenario
from app.services.alert_service import alert_cache
from app.services.business_model import build_all_business_models
from app.services.dashboard_service import reset_dashboard_state
from app.services.health_engine import health_engine
from app.services.live_state import live_state
from app.services.telemetry_service import telemetry_service
from app.utils.time import utc_now
from app.websocket.manager import connection_manager

# =============================================================================
# Digital Twin control
# =============================================================================

twin_router = APIRouter(prefix="/twin", tags=["Digital Twin Engine"])


def _engine():
    """Resolve the running engine.

    Imported lazily from application state rather than held as a module global,
    so the engine's lifetime stays owned by the application lifespan.
    """
    from app.main import get_twin_engine

    engine_instance = get_twin_engine()
    if engine_instance is None:
        raise InvalidStateError("The Digital Twin Engine is not initialised.")
    return engine_instance


class TwinScenarioRequest(BaseModel):
    """Drive one virtual device into a specific behaviour."""

    asset_id: uuid.UUID
    scenario: TwinScenario


@twin_router.get("/status", response_model=Envelope[dict[str, Any]], summary="Engine status")
async def twin_status() -> Envelope[dict[str, Any]]:
    """Engine state, fleet composition, throughput and storage tiers."""
    engine_instance = _engine()
    return envelope(
        {
            **engine_instance.status(),
            "telemetry": telemetry_service.status(),
            "intelligence": intelligence_runner.status(),
            "websocket": connection_manager.status(),
            "health_engine": {"tracked_assets": health_engine.tracked_assets},
            "storage": await rollup_health(),
        }
    )


@twin_router.get(
    "/devices", response_model=Envelope[list[dict[str, Any]]], summary="Device diagnostics"
)
async def twin_devices(
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
) -> Envelope[list[dict[str, Any]]]:
    """Per-device scenario and condition, for engineering inspection."""
    return envelope(_engine().device_snapshots(limit))


@twin_router.post("/start", response_model=Envelope[dict[str, Any]], summary="Start the engine")
async def twin_start() -> Envelope[dict[str, Any]]:
    """Begin generating telemetry."""
    engine_instance = _engine()
    await engine_instance.start()
    return envelope(engine_instance.status(), message="Digital Twin Engine started.")


@twin_router.post("/stop", response_model=Envelope[dict[str, Any]], summary="Pause the engine")
async def twin_stop() -> Envelope[dict[str, Any]]:
    """Stop emitting without discarding accumulated device state."""
    engine_instance = _engine()
    await engine_instance.pause()
    return envelope(engine_instance.status(), message="Digital Twin Engine paused.")


@twin_router.post("/reset", response_model=Envelope[dict[str, Any]], summary="Reset the fleet")
async def twin_reset() -> Envelope[dict[str, Any]]:
    """Rebuild every virtual device and clear derived dashboard state."""
    engine_instance = _engine()
    await engine_instance.reset()
    live_state.reset()
    # Health is smoothed per asset across readings; carrying those scores over
    # a fleet rebuild would blend the old devices' condition into the new ones.
    health_engine.reset()
    reset_dashboard_state()
    return envelope(engine_instance.status(), message="Digital Twin Engine reset.")


@twin_router.post(
    "/scenario", response_model=Envelope[dict[str, Any]], summary="Force a scenario"
)
async def twin_scenario(payload: TwinScenarioRequest) -> Envelope[dict[str, Any]]:
    """Drive a device into a behaviour on demand, for demonstration."""
    engine_instance = _engine()
    if not engine_instance.force_scenario(payload.asset_id, payload.scenario):
        raise NotFoundError(f"No virtual device bound to asset {payload.asset_id}.")
    return envelope(
        {"asset_id": str(payload.asset_id), "scenario": payload.scenario.value},
        message=f"Device driven into {payload.scenario.value}.",
    )


# =============================================================================
# Reports
# =============================================================================

reports_router = APIRouter(prefix="/reports", tags=["Reports"])


class ReportDefinition(BaseModel):
    """A report the platform can produce."""

    key: str
    name: str
    description: str
    formats: list[str]
    columns: list[str]


#: Available reports. Adding one means adding an entry and a builder below.
REPORTS: dict[str, ReportDefinition] = {
    "energy": ReportDefinition(
        key="energy",
        name="Energy Report",
        description="Consumption, cost and metering coverage across the fleet.",
        formats=["csv", "json"],
        columns=["asset_code", "name", "asset_type", "energy_kwh", "power_w", "cost"],
    ),
    "health": ReportDefinition(
        key="health",
        name="Health Report",
        description="Condition, connectivity and business score for every asset.",
        formats=["csv", "json"],
        columns=[
            "asset_code", "name", "asset_type", "health_score", "health_state",
            "operational_state", "connectivity_state", "business_score",
        ],
    ),
    "maintenance": ReportDefinition(
        key="maintenance",
        name="Maintenance Report",
        description="Outstanding alerts and efficiency by asset.",
        formats=["csv", "json"],
        columns=["asset_code", "name", "asset_type", "active_alerts", "efficiency", "health_state"],
    ),
    "telemetry": ReportDefinition(
        key="telemetry",
        name="Telemetry Export",
        description="Raw readings within an explicit window.",
        formats=["csv", "json"],
        columns=[
            "time", "asset_code", "voltage_v", "current_a", "power_w",
            "energy_kwh", "temperature_c", "power_factor", "health_score",
        ],
    ),
}


@reports_router.get(
    "", response_model=Envelope[list[ReportDefinition]], summary="Available reports"
)
async def list_reports() -> Envelope[list[ReportDefinition]]:
    """Report catalogue with the formats each supports."""
    return envelope(list(REPORTS.values()))


async def _report_rows(
    key: str, session: SessionDep, window: WindowDep
) -> list[dict[str, Any]]:
    """Materialise a report's rows."""
    if key == "telemetry":
        rows = (
            await session.execute(
                select(Telemetry, Asset)
                .join(Asset, Telemetry.asset_id == Asset.id)
                .where(Telemetry.time >= window.start, Telemetry.time <= window.end)
                .order_by(Telemetry.time.desc())
                .limit(20_000)
            )
        ).all()
        return [
            {
                "time": telemetry.time.isoformat(),
                "asset_code": asset.asset_code,
                "voltage_v": telemetry.voltage_v,
                "current_a": telemetry.current_a,
                "power_w": telemetry.power_w,
                "energy_kwh": telemetry.energy_kwh,
                "temperature_c": telemetry.temperature_c,
                "power_factor": telemetry.power_factor,
                "health_score": telemetry.health_score,
            }
            for telemetry, asset in rows
        ]

    models = build_all_business_models(alert_cache.per_asset)
    columns = REPORTS[key].columns
    return [
        {
            column: getattr(model, column, None)
            if column != "name"
            else model.name
            for column in columns
        }
        for model in models
    ]


@reports_router.post("/export", summary="Export a report")
async def export_report(
    session: SessionDep,
    window: WindowDep,
    report: Annotated[str, Query(description="Report key from the catalogue.")] = "health",
    export_format: Annotated[
        str, Query(alias="format", pattern="^(csv|json)$")
    ] = "csv",
) -> Response:
    """Generate a report and return it as a downloadable file.

    CSV and JSON are produced natively. PDF and spreadsheet rendering are part
    of the reporting phase and are deliberately absent rather than stubbed —
    an endpoint that returns an empty or fake document is worse than one that
    declines clearly.
    """
    definition = REPORTS.get(report)
    if definition is None:
        raise NotFoundError(
            f"Unknown report '{report}'. Available: {', '.join(sorted(REPORTS))}."
        )

    rows = await _report_rows(report, session, window)
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    filename = f"intelora-{report}-{stamp}.{export_format}"

    if export_format == "json":
        body = json.dumps(
            {
                "report": definition.name,
                "generated_at": utc_now().isoformat(),
                "window": {"start": window.start.isoformat(), "end": window.end.isoformat()},
                "rows": rows,
            },
            default=str,
            indent=2,
        )
        media_type = "application/json"
    else:
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=definition.columns, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
        body = buffer.getvalue()
        media_type = "text/csv"

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =============================================================================
# Settings
# =============================================================================

settings_router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsPayload(BaseModel):
    """Platform preferences.

    Theme and language are stored server-side because the SSOT places them on
    the user profile; until authentication exists they are platform-wide
    defaults that the frontend falls back to.
    """

    theme: str = Field(default="dark", pattern="^(dark|light|system)$")
    language: str = Field(default="en", max_length=8)
    organization_name: str = Field(default="INTELORA Industries", max_length=160)
    notifications_enabled: bool = True
    notify_on_critical: bool = True
    notify_on_warning: bool = True
    energy_tariff_per_kwh: float = Field(default=0.14, ge=0)
    currency_code: str = Field(default="USD", max_length=8)
    sidebar_collapsed: bool = False
    reduced_motion: bool = False


SETTINGS_KEY = "platform.preferences"


async def _load_settings(session: SessionDep) -> SettingsPayload:
    record = await session.scalar(
        select(SystemSetting).where(SystemSetting.key == SETTINGS_KEY)
    )
    if record is None or not isinstance(record.value, dict):
        return SettingsPayload(
            energy_tariff_per_kwh=app_settings.energy_tariff_per_kwh,
            currency_code=app_settings.currency_code,
        )
    return SettingsPayload.model_validate(record.value)


@settings_router.get(
    "", response_model=Envelope[SettingsPayload], summary="Read platform settings"
)
async def get_settings(session: SessionDep) -> Envelope[SettingsPayload]:
    """Current preferences, falling back to environment defaults."""
    return envelope(await _load_settings(session))


@settings_router.put(
    "", response_model=Envelope[SettingsPayload], summary="Update platform settings"
)
async def update_settings(
    payload: SettingsPayload, session: SessionDep
) -> Envelope[SettingsPayload]:
    """Persist preferences, upserting the single settings record."""
    record = await session.scalar(
        select(SystemSetting).where(SystemSetting.key == SETTINGS_KEY)
    )
    if record is None:
        record = SystemSetting(
            key=SETTINGS_KEY,
            category="platform",
            description="Platform-wide preferences.",
        )
        session.add(record)

    record.value = payload.model_dump()
    await session.commit()

    live_state.set_organization(payload.organization_name)
    return envelope(payload, message="Settings saved.")


# =============================================================================
# Health
# =============================================================================

system_router = APIRouter(tags=["System"])


@system_router.get("/health", response_model=HealthCheck, summary="Liveness probe")
async def health() -> HealthCheck:
    """Container and orchestrator health check.

    Returns the bare model rather than the envelope: probes expect a flat
    document, and wrapping it would make the check itself harder to read.
    """
    database_connected = True
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")
    except Exception:
        database_connected = False

    twin_running = False
    try:
        twin_running = _engine().is_running
    except Exception:
        twin_running = False

    return HealthCheck(
        status="ok" if database_connected else "degraded",
        version=app_settings.app_version,
        environment=app_settings.intelora_env,
        database_connected=database_connected,
        twin_running=twin_running,
        timestamp=utc_now(),
    )

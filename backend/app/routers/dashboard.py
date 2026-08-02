"""Dashboard endpoints.

Page-shaped rather than resource-shaped: the Cockpit is served by four
aggregate payloads instead of composing a dozen resource calls, which is what
keeps first paint inside the five-second comprehension target.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.intelligence.summaries import build_intelligence_summary
from app.models import Asset, Telemetry
from app.routers.deps import SessionDep
from app.schemas.common import Envelope, envelope
from app.schemas.dashboard import (
    ChartBundle,
    CockpitOverview,
    KpiValue,
    RecentTelemetryRow,
)
from app.schemas.intelligence import IntelligenceSummary
from app.services.dashboard_service import (
    build_chart_bundle,
    build_cockpit_overview,
    build_energy_summary,
    build_kpis,
)
from app.services.alert_service import alert_cache
from app.services.business_model import build_all_business_models

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/overview",
    response_model=Envelope[CockpitOverview],
    summary="Enterprise Cockpit",
    description="Complete Mission Control payload: system verdict, KPIs, asset "
    "summaries, every intelligence layer's headline, energy and alerts.",
)
async def get_overview(session: SessionDep) -> Envelope[CockpitOverview]:
    """Assemble the full Cockpit view in a single response."""
    intelligence = await build_intelligence_summary(session)
    overview = await build_cockpit_overview(session, intelligence)
    return envelope(overview)


@router.get(
    "/kpi",
    response_model=Envelope[list[KpiValue]],
    summary="Executive KPI cards",
)
async def get_kpis(session: SessionDep) -> Envelope[list[KpiValue]]:
    """The nine KPI cards, each carrying the route it navigates to."""
    intelligence = await build_intelligence_summary(session)
    models = build_all_business_models(alert_cache.per_asset)
    energy = build_energy_summary(models)

    average_oee = (
        intelligence.oee.enterprise.oee * 100.0 if intelligence.oee.enterprise else None
    )

    return envelope(
        build_kpis(
            models,
            energy=energy,
            average_oee=average_oee,
            cost_saving=intelligence.prescriptive.total_cost_saving,
        )
    )


@router.get(
    "/charts",
    response_model=Envelope[ChartBundle],
    summary="Cockpit chart data",
    description="Every Cockpit chart in one payload so they resolve as a single "
    "coordinated wave rather than a dozen independent loading states.",
)
async def get_charts() -> Envelope[ChartBundle]:
    """Trend series and distributions for the Cockpit."""
    return envelope(build_chart_bundle())


@router.get(
    "/intelligence",
    response_model=Envelope[IntelligenceSummary],
    summary="All six intelligence layers",
)
async def get_intelligence(session: SessionDep) -> Envelope[IntelligenceSummary]:
    """Headline verdict from each layer."""
    return envelope(await build_intelligence_summary(session))


@router.get(
    "/recent",
    response_model=Envelope[list[RecentTelemetryRow]],
    summary="Recent telemetry",
    description="Newest readings across the fleet, for the live telemetry table.",
)
async def get_recent(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 40,
) -> Envelope[list[RecentTelemetryRow]]:
    """Most recent readings, joined to asset identity for display."""
    rows = (
        await session.execute(
            select(Telemetry, Asset)
            .join(Asset, Telemetry.asset_id == Asset.id)
            .order_by(Telemetry.time.desc())
            .limit(limit)
        )
    ).all()

    return envelope(
        [
            RecentTelemetryRow(
                time=telemetry.time,
                asset_id=asset.id,
                asset_code=asset.asset_code,
                asset_name=asset.name,
                asset_type=asset.asset_type,
                voltage_v=telemetry.voltage_v,
                current_a=telemetry.current_a,
                power_w=telemetry.power_w,
                energy_kwh=telemetry.energy_kwh,
                temperature_c=telemetry.temperature_c,
                frequency_hz=telemetry.frequency_hz,
                power_factor=telemetry.power_factor,
                health_score=telemetry.health_score,
                health_state=telemetry.health_state,
                quality=str(telemetry.quality),
            )
            for telemetry, asset in rows
        ]
    )

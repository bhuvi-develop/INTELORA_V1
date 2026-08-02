"""API routers.

Assembled into one versioned router so that ``main`` mounts a single object and
the version prefix is declared exactly once.
"""

from fastapi import APIRouter

from app.config import settings
from app.routers.alerts import router as alerts_router
from app.routers.assets import router as assets_router
from app.routers.dashboard import router as dashboard_router
from app.routers.intelligence import (
    anomaly_router,
    apm_router,
    oee_router,
    predictive_router,
    prescriptive_router,
    preventive_router,
)
from app.routers.operations import (
    reports_router,
    settings_router,
    system_router,
    twin_router,
)
from app.routers.telemetry import router as telemetry_router

api_router = APIRouter(prefix=settings.api_v1_prefix)

for _router in (
    dashboard_router,
    assets_router,
    telemetry_router,
    alerts_router,
    anomaly_router,
    predictive_router,
    preventive_router,
    prescriptive_router,
    apm_router,
    oee_router,
    twin_router,
    reports_router,
    settings_router,
):
    api_router.include_router(_router)

__all__ = ["api_router", "system_router"]

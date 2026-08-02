"""INTELORA backend entry point.

Wires the layers together and owns their lifetimes:

``Digital Twin → Telemetry Service → Database → Intelligence → WebSocket``

The twin is constructed with the telemetry service as its sink, which is the
single seam that lets a real sensor gateway replace it later without any other
module changing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.database.init_db import initialise_database
from app.database.session import dispose_engine, session_scope
from app.models import Organization
from app.digital_twin.engine import DigitalTwinEngine
from app.intelligence.runner import intelligence_runner
from app.routers import api_router, system_router
from app.services.alert_service import refresh_cache
from app.services.live_state import live_state
from app.services.telemetry_service import telemetry_service
from app.websocket.router import router as websocket_router

logger = get_logger(__name__)

#: Owned by the lifespan; read through :func:`get_twin_engine`.
_twin_engine: DigitalTwinEngine | None = None


def get_twin_engine() -> DigitalTwinEngine | None:
    """Return the running Digital Twin Engine, if the application has started."""
    return _twin_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start and stop every long-lived subsystem in dependency order."""
    global _twin_engine

    configure_logging()
    logger.info(
        "INTELORA starting",
        extra={"environment": settings.intelora_env, "version": settings.app_version},
    )

    # 1. Schema, hypertable and asset registry.
    await initialise_database()

    # 2. Cache asset identities so the live path needs no joins.
    await telemetry_service.refresh_registry()

    async with session_scope() as session:
        organization = await session.scalar(select(Organization).limit(1))
        if organization is not None:
            live_state.set_organization(organization.name)
        await refresh_cache(session)

    # 3. The twin publishes into the Telemetry Layer, never directly to storage.
    _twin_engine = DigitalTwinEngine(sink=telemetry_service.ingest_batch)
    await _twin_engine.load_fleet()

    if settings.twin_enabled:
        await _twin_engine.start()
    else:
        logger.warning(
            "Digital Twin Engine disabled by configuration; the platform will "
            "render its empty states until a data source is attached."
        )

    # 4. Intelligence runs over whatever the Telemetry Layer has collected.
    await intelligence_runner.start()

    logger.info("INTELORA ready", extra={"assets": live_state.asset_count})

    try:
        yield
    finally:
        logger.info("INTELORA shutting down")
        await intelligence_runner.stop()
        if _twin_engine is not None:
            await _twin_engine.stop()
        await dispose_engine()
        _twin_engine = None


app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(system_router)
app.include_router(api_router)
app.include_router(websocket_router)


@app.get("/", tags=["System"], summary="Service identity")
async def root() -> dict[str, str]:
    """Minimal service descriptor, useful behind a load balancer."""
    return {
        "platform": settings.app_name,
        "description": "Enterprise AIOT Intelligence Platform",
        "version": settings.app_version,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
        "live": "/ws/live",
    }

"""Asset endpoints.

Serves both views of an asset: its identity and telemetry capabilities, and its
projection into the unified business model that dashboard surfaces bind to.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError
from app.digital_twin.profiles import capabilities_for
from app.models import Asset
from app.models.organization import AssetGroup, Location, Organization
from app.routers.deps import PaginationDep, SessionDep
from app.schemas.asset import (
    AssetBusinessModel,
    AssetCreate,
    AssetRead,
    AssetScope,
    AssetTypeSummary,
    AssetUpdate,
)
from app.schemas.common import Envelope, Page, PageMeta, envelope
from app.schemas.enums import AssetType, ConnectivityState, HealthState, OperationalState
from app.schemas.telemetry import TelemetryIngest
from app.services.alert_service import alert_cache
from app.services.business_model import (
    build_all_business_models,
    build_business_model,
    summarise_asset_types,
)
from app.services.live_state import live_state
from app.services.telemetry_service import telemetry_service

router = APIRouter(prefix="/assets", tags=["Assets"])


def _to_read(asset: Asset) -> AssetRead:
    """Project an ORM asset, flattening its scope for display."""
    location = asset.location
    group = asset.asset_group

    return AssetRead(
        id=asset.id,
        asset_code=asset.asset_code,
        name=asset.name,
        asset_type=asset.asset_type,
        manufacturer=asset.manufacturer,
        model=asset.model,
        serial_number=asset.serial_number,
        rated_power_w=asset.rated_power_w,
        rated_voltage_v=asset.rated_voltage_v,
        commissioned_at=asset.commissioned_at,
        health_score=asset.health_score,
        health_state=asset.health_state,
        operational_state=asset.operational_state,
        connectivity_state=asset.connectivity_state,
        lifecycle_stage=asset.lifecycle_stage,
        last_seen_at=asset.last_seen_at,
        operating_hours=asset.operating_hours,
        lifetime_energy_kwh=asset.lifetime_energy_kwh,
        relay_operations=asset.relay_operations,
        scope=AssetScope(
            organization_id=asset.organization_id,
            organization_name=asset.organization.name if asset.organization else None,
            location_id=asset.location_id,
            location_name=location.name if location else None,
            building=location.building if location else None,
            department=location.department if location else None,
            asset_group_id=asset.asset_group_id,
            asset_group_name=group.name if group else None,
        ),
        capabilities=capabilities_for(asset.asset_type),
    )


@router.get(
    "",
    response_model=Envelope[Page[AssetRead]],
    summary="List assets",
    description="Paginated asset registry. Health, operational and connectivity "
    "state filter independently — they are three separate dimensions.",
)
async def list_assets(
    session: SessionDep,
    pagination: PaginationDep,
    asset_type: Annotated[AssetType | None, Query()] = None,
    health: Annotated[HealthState | None, Query()] = None,
    operational: Annotated[OperationalState | None, Query()] = None,
    connectivity: Annotated[ConnectivityState | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    sort: Annotated[str, Query(pattern="^(asset_code|name|health_score|last_seen_at)$")] = "asset_code",
    direction: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
) -> Envelope[Page[AssetRead]]:
    """Filtered, sorted, paginated asset list."""
    query = select(Asset).options(
        selectinload(Asset.location),
        selectinload(Asset.asset_group),
        selectinload(Asset.organization),
    )
    count_query = select(func.count()).select_from(Asset)

    conditions = []
    if asset_type is not None:
        conditions.append(Asset.asset_type == asset_type)
    if health is not None:
        conditions.append(Asset.health_state == health)
    if operational is not None:
        conditions.append(Asset.operational_state == operational)
    if connectivity is not None:
        conditions.append(Asset.connectivity_state == connectivity)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(Asset.name.ilike(pattern) | Asset.asset_code.ilike(pattern))

    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    column = getattr(Asset, sort)
    query = query.order_by(column.desc() if direction == "desc" else column.asc())

    total = int(await session.scalar(count_query) or 0)
    rows = (
        await session.scalars(
            query.offset(pagination.offset).limit(pagination.page_size)
        )
    ).all()

    return envelope(
        Page[AssetRead](
            items=[_to_read(asset) for asset in rows],
            meta=PageMeta.build(
                page=pagination.page, page_size=pagination.page_size, total_items=total
            ),
        )
    )


@router.get(
    "/business",
    response_model=Envelope[list[AssetBusinessModel]],
    summary="Fleet in the unified business model",
    description="Every asset projected into the same contract, whatever it "
    "reports. This is what dashboard surfaces bind to.",
)
async def list_business_models(
    asset_type: Annotated[AssetType | None, Query()] = None,
    health: Annotated[HealthState | None, Query()] = None,
) -> Envelope[list[AssetBusinessModel]]:
    """Business-model projection of the fleet, filtered in memory."""
    models = build_all_business_models(alert_cache.per_asset)

    if asset_type is not None:
        models = [m for m in models if m.asset_type is asset_type]
    if health is not None:
        models = [m for m in models if m.health_state is health]

    models.sort(key=lambda m: m.business_score)
    return envelope(models)


@router.get(
    "/summary",
    response_model=Envelope[list[AssetTypeSummary]],
    summary="Asset category summaries",
    description="Fleet roll-up per asset type, backing the three premium cards.",
)
async def get_summaries() -> Envelope[list[AssetTypeSummary]]:
    """One summary per asset category, with capabilities attached."""
    return envelope(summarise_asset_types(build_all_business_models(alert_cache.per_asset)))


@router.get(
    "/{asset_id}",
    response_model=Envelope[AssetRead],
    summary="Asset detail",
)
async def get_asset(asset_id: uuid.UUID, session: SessionDep) -> Envelope[AssetRead]:
    """One asset with its full identity and scope."""
    asset = await session.scalar(
        select(Asset)
        .options(
            selectinload(Asset.location),
            selectinload(Asset.asset_group),
            selectinload(Asset.organization),
        )
        .where(Asset.id == asset_id)
    )
    if asset is None:
        raise NotFoundError(f"Asset {asset_id} does not exist.")
    return envelope(_to_read(asset))


@router.get(
    "/{asset_id}/business",
    response_model=Envelope[AssetBusinessModel],
    summary="Asset in the unified business model",
)
async def get_asset_business(asset_id: uuid.UUID) -> Envelope[AssetBusinessModel]:
    """Business-model projection for one asset."""
    identity = live_state.identity(asset_id)
    if identity is None:
        raise NotFoundError(f"Asset {asset_id} does not exist.")
    return envelope(
        build_business_model(identity, active_alerts=alert_cache.count_for(asset_id))
    )


@router.get(
    "/{asset_id}/telemetry",
    response_model=Envelope[TelemetryIngest | None],
    summary="Latest reading for one asset",
    description="The newest reading held in memory, including the channels "
    "specific to this asset category — charge state, battery level and cycle "
    "count for chargers, conditioned-space temperature for air conditioners.",
)
async def get_asset_telemetry(asset_id: uuid.UUID) -> Envelope[TelemetryIngest | None]:
    """Serve one asset's latest reading from the live snapshot.

    Reads from memory rather than the hypertable: this is the "what is it doing
    right now" question, and the answer is one row that the Telemetry Layer
    already holds.
    """
    if live_state.identity(asset_id) is None:
        raise NotFoundError(f"Asset {asset_id} does not exist.")

    reading = live_state.latest(asset_id)
    if reading is None:
        return envelope(None, message="No reading received from this asset yet.")
    return envelope(reading)


@router.post(
    "",
    response_model=Envelope[AssetRead],
    status_code=status.HTTP_201_CREATED,
    summary="Commission an asset",
)
async def create_asset(payload: AssetCreate, session: SessionDep) -> Envelope[AssetRead]:
    """Register a new asset and refresh the live registry."""
    existing = await session.scalar(
        select(Asset).where(Asset.asset_code == payload.asset_code)
    )
    if existing is not None:
        raise ConflictError(f"Asset code {payload.asset_code} is already in use.")

    organization = await session.get(Organization, payload.organization_id)
    if organization is None:
        raise NotFoundError(f"Organization {payload.organization_id} does not exist.")

    if payload.location_id and await session.get(Location, payload.location_id) is None:
        raise NotFoundError(f"Location {payload.location_id} does not exist.")
    if payload.asset_group_id and await session.get(AssetGroup, payload.asset_group_id) is None:
        raise NotFoundError(f"Asset group {payload.asset_group_id} does not exist.")

    asset = Asset(**payload.model_dump())
    session.add(asset)
    await session.commit()

    # The live registry is a cache of this table; it must not drift from it.
    await telemetry_service.refresh_registry()

    refreshed = await session.scalar(
        select(Asset)
        .options(
            selectinload(Asset.location),
            selectinload(Asset.asset_group),
            selectinload(Asset.organization),
        )
        .where(Asset.id == asset.id)
    )
    return envelope(_to_read(refreshed or asset), message="Asset commissioned.")


@router.put(
    "/{asset_id}",
    response_model=Envelope[AssetRead],
    summary="Update an asset",
)
async def update_asset(
    asset_id: uuid.UUID, payload: AssetUpdate, session: SessionDep
) -> Envelope[AssetRead]:
    """Apply a partial update. Unset fields are left untouched."""
    asset = await session.scalar(
        select(Asset)
        .options(
            selectinload(Asset.location),
            selectinload(Asset.asset_group),
            selectinload(Asset.organization),
        )
        .where(Asset.id == asset_id)
    )
    if asset is None:
        raise NotFoundError(f"Asset {asset_id} does not exist.")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)

    await session.commit()
    await telemetry_service.refresh_registry()
    return envelope(_to_read(asset), message="Asset updated.")


@router.delete(
    "/{asset_id}",
    response_model=Envelope[None],
    summary="Decommission an asset",
)
async def delete_asset(asset_id: uuid.UUID, session: SessionDep) -> Envelope[None]:
    """Remove an asset and everything that references it."""
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError(f"Asset {asset_id} does not exist.")

    await session.delete(asset)
    await session.commit()
    await telemetry_service.refresh_registry()
    return envelope(None, message="Asset decommissioned.")

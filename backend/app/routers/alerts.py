"""Alert endpoints.

Severity and lifecycle filter independently throughout, which is the point of
keeping them as two columns rather than one status field.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.routers.deps import PaginationDep, SessionDep
from app.schemas.alert import AlertRead, AlertSummary, AlertUpdate
from app.schemas.common import Envelope, Page, envelope
from app.schemas.enums import AlertSeverity, AlertStatus, AssetType
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get(
    "",
    response_model=Envelope[Page[AlertRead]],
    summary="Alert queue",
)
async def list_alerts(
    session: SessionDep,
    pagination: PaginationDep,
    severity: Annotated[AlertSeverity | None, Query()] = None,
    status: Annotated[AlertStatus | None, Query()] = None,
    asset_id: Annotated[uuid.UUID | None, Query()] = None,
    asset_type: Annotated[AssetType | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=160)] = None,
    since: Annotated[datetime | None, Query()] = None,
) -> Envelope[Page[AlertRead]]:
    """Filtered, paginated alert queue, newest first."""
    page = await alert_service.list_alerts(
        session,
        page=pagination.page,
        page_size=pagination.page_size,
        severity=severity,
        status=status,
        asset_id=asset_id,
        asset_type=asset_type,
        search=search,
        since=since,
    )
    return envelope(page)


@router.get(
    "/summary",
    response_model=Envelope[AlertSummary],
    summary="Alert counts",
    description="Severity and lifecycle counts plus the most recent alerts, "
    "backing the Cockpit section and the navbar badge.",
)
async def get_summary(session: SessionDep) -> Envelope[AlertSummary]:
    """Recompute and return the alert summary."""
    return envelope(await alert_service.refresh_cache(session))


@router.get(
    "/{alert_id}",
    response_model=Envelope[AlertRead],
    summary="Alert detail",
)
async def get_alert(alert_id: uuid.UUID, session: SessionDep) -> Envelope[AlertRead]:
    """One alert, with the evidence that raised it."""
    return envelope(await alert_service.get_alert(session, alert_id))


@router.put(
    "/{alert_id}",
    response_model=Envelope[AlertRead],
    summary="Acknowledge, resolve or assign",
    description="Lifecycle transitions are validated: an alert cannot move "
    "backwards, and a resolved alert is terminal.",
)
async def update_alert(
    alert_id: uuid.UUID, payload: AlertUpdate, session: SessionDep
) -> Envelope[AlertRead]:
    """Apply a lifecycle transition or assignment."""
    alert = await alert_service.update_alert(session, alert_id, payload)
    return envelope(alert, message="Alert updated.")


@router.delete(
    "/{alert_id}",
    response_model=Envelope[None],
    summary="Dismiss an alert",
)
async def delete_alert(alert_id: uuid.UUID, session: SessionDep) -> Envelope[None]:
    """Remove an alert permanently."""
    await alert_service.delete_alert(session, alert_id)
    return envelope(None, message="Alert dismissed.")

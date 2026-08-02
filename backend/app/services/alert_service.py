"""Alert lifecycle and the in-memory alert cache.

Alerts are raised by the Anomaly Detection layer and worked by operators.
Severity and lifecycle are handled as independent axes throughout — an alert
can be critical *and* acknowledged, and both filters must work at once.

The per-asset active counts are cached because the live tick needs them every
second, and a ``GROUP BY`` over the alert table at 1 Hz per connected client is
not a cost the platform should pay for a number that changes rarely.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import Alert, Asset
from app.schemas.alert import AlertRead, AlertSummary, AlertUpdate
from app.schemas.common import Page, PageMeta
from app.schemas.enums import AlertSeverity, AlertStatus, AssetType
from app.utils.time import start_of_utc_day, utc_now
from app.websocket.manager import MessageType, connection_manager

logger = get_logger(__name__)

#: Lifecycle transitions the API will accept. A resolved alert is terminal:
#: reopening it would break the audit trail, so a recurrence must raise a new
#: alert rather than resurrect an old one.
ALLOWED_TRANSITIONS: dict[AlertStatus, set[AlertStatus]] = {
    AlertStatus.ACTIVE: {AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED},
    AlertStatus.ACKNOWLEDGED: {AlertStatus.RESOLVED},
    AlertStatus.RESOLVED: set(),
}


class AlertCache:
    """Cached alert counts, refreshed whenever the alert table changes."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._per_asset: dict[uuid.UUID, int] = {}
        self._summary = AlertSummary()

    def replace(self, per_asset: dict[uuid.UUID, int], summary: AlertSummary) -> None:
        with self._lock:
            self._per_asset = per_asset
            self._summary = summary

    @property
    def per_asset(self) -> dict[uuid.UUID, int]:
        with self._lock:
            return dict(self._per_asset)

    @property
    def summary(self) -> AlertSummary:
        with self._lock:
            return self._summary

    def count_for(self, asset_id: uuid.UUID) -> int:
        return self._per_asset.get(asset_id, 0)


alert_cache = AlertCache()


def _to_read(alert: Alert) -> AlertRead:
    """Project an ORM alert, flattening asset identity for display."""
    asset = alert.asset
    return AlertRead(
        id=alert.id,
        asset_id=alert.asset_id,
        asset_code=asset.asset_code if asset else None,
        asset_name=asset.name if asset else None,
        asset_type=asset.asset_type if asset else None,
        severity=alert.severity,
        status=alert.status,
        fault_type=alert.fault_type,
        title=alert.title,
        message=alert.message,
        channel=alert.channel,
        observed_value=alert.observed_value,
        expected_min=alert.expected_min,
        expected_max=alert.expected_max,
        anomaly_result_id=alert.anomaly_result_id,
        triggered_at=alert.triggered_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
        assigned_to=alert.assigned_to,
    )


async def refresh_cache(session: AsyncSession) -> AlertSummary:
    """Recompute cached counts and the Cockpit alert summary."""
    open_statuses = (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED)

    per_asset_rows = (
        await session.execute(
            select(Alert.asset_id, func.count())
            .where(Alert.status.in_(open_statuses))
            .group_by(Alert.asset_id)
        )
    ).all()
    per_asset = {asset_id: int(count) for asset_id, count in per_asset_rows}

    status_rows = (
        await session.execute(select(Alert.status, func.count()).group_by(Alert.status))
    ).all()
    by_status = {status: int(count) for status, count in status_rows}

    severity_rows = (
        await session.execute(
            select(Alert.severity, func.count())
            .where(Alert.status.in_(open_statuses))
            .group_by(Alert.severity)
        )
    ).all()
    by_severity = {severity: int(count) for severity, count in severity_rows}

    recent = (
        await session.scalars(
            select(Alert)
            .options(selectinload(Alert.asset))
            .order_by(Alert.triggered_at.desc())
            .limit(8)
        )
    ).all()

    summary = AlertSummary(
        total=sum(by_status.values()),
        active=by_status.get(AlertStatus.ACTIVE, 0),
        acknowledged=by_status.get(AlertStatus.ACKNOWLEDGED, 0),
        resolved=by_status.get(AlertStatus.RESOLVED, 0),
        critical=by_severity.get(AlertSeverity.CRITICAL, 0),
        warning=by_severity.get(AlertSeverity.WARNING, 0),
        information=by_severity.get(AlertSeverity.INFORMATION, 0),
        recent=[_to_read(alert) for alert in recent],
    )

    alert_cache.replace(per_asset, summary)
    return summary


async def list_alerts(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    severity: AlertSeverity | None = None,
    status: AlertStatus | None = None,
    asset_id: uuid.UUID | None = None,
    asset_type: AssetType | None = None,
    search: str | None = None,
    since: datetime | None = None,
) -> Page[AlertRead]:
    """Paginated, filtered alert queue.

    Severity and status filter independently, which is the whole point of
    keeping them as separate columns.
    """
    conditions = []
    if severity is not None:
        conditions.append(Alert.severity == severity)
    if status is not None:
        conditions.append(Alert.status == status)
    if asset_id is not None:
        conditions.append(Alert.asset_id == asset_id)
    if since is not None:
        conditions.append(Alert.triggered_at >= since)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(Alert.title.ilike(pattern) | Alert.message.ilike(pattern))

    base = select(Alert).options(selectinload(Alert.asset))
    count_query = select(func.count()).select_from(Alert)

    if asset_type is not None:
        base = base.join(Asset, Alert.asset_id == Asset.id).where(
            Asset.asset_type == asset_type
        )
        count_query = count_query.join(Asset, Alert.asset_id == Asset.id).where(
            Asset.asset_type == asset_type
        )

    for condition in conditions:
        base = base.where(condition)
        count_query = count_query.where(condition)

    total = int(await session.scalar(count_query) or 0)

    rows = (
        await session.scalars(
            base.order_by(Alert.triggered_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return Page[AlertRead](
        items=[_to_read(alert) for alert in rows],
        meta=PageMeta.build(page=page, page_size=page_size, total_items=total),
    )


async def get_alert(session: AsyncSession, alert_id: uuid.UUID) -> AlertRead:
    """Fetch one alert, for the detail route."""
    alert = await session.scalar(
        select(Alert).options(selectinload(Alert.asset)).where(Alert.id == alert_id)
    )
    if alert is None:
        raise NotFoundError(f"Alert {alert_id} does not exist.")
    return _to_read(alert)


async def update_alert(
    session: AsyncSession, alert_id: uuid.UUID, payload: AlertUpdate
) -> AlertRead:
    """Acknowledge, resolve or assign an alert.

    Transitions are validated so the lifecycle cannot move backwards.
    """
    alert = await session.scalar(
        select(Alert).options(selectinload(Alert.asset)).where(Alert.id == alert_id)
    )
    if alert is None:
        raise NotFoundError(f"Alert {alert_id} does not exist.")

    now = utc_now()

    if payload.status is not None and payload.status is not alert.status:
        if payload.status not in ALLOWED_TRANSITIONS[alert.status]:
            raise ConflictError(
                f"An alert cannot move from {alert.status.value} to {payload.status.value}."
            )
        alert.status = payload.status
        if payload.status is AlertStatus.ACKNOWLEDGED:
            alert.acknowledged_at = now
        elif payload.status is AlertStatus.RESOLVED:
            alert.resolved_at = now
            if alert.acknowledged_at is None:
                alert.acknowledged_at = now

    if payload.assigned_to is not None:
        alert.assigned_to = payload.assigned_to.strip() or None

    await session.flush()
    await session.commit()

    summary = await refresh_cache(session)
    await connection_manager.broadcast(MessageType.ALERT, summary.model_dump(mode="json"))

    return _to_read(alert)


async def delete_alert(session: AsyncSession, alert_id: uuid.UUID) -> None:
    """Dismiss an alert permanently."""
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise NotFoundError(f"Alert {alert_id} does not exist.")

    await session.delete(alert)
    await session.commit()

    summary = await refresh_cache(session)
    await connection_manager.broadcast(MessageType.ALERT, summary.model_dump(mode="json"))


async def alerts_raised_today(session: AsyncSession) -> int:
    """Count of alerts raised since midnight UTC."""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Alert)
            .where(Alert.triggered_at >= start_of_utc_day())
        )
        or 0
    )

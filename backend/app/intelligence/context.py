"""Shared computation context for the intelligence layers.

The six layers run as one pass and share their inputs. Gathering telemetry
statistics once and handing them to every layer avoids six near-identical
window queries per cycle, and guarantees all six reason about exactly the same
data — a layer disagreeing with the one below it because they read the table a
second apart would be very hard to debug.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Alert, AnomalyResult, Telemetry
from app.schemas.enums import (
    AlertStatus,
    AnomalyStatus,
    DataQuality,
    OperationalState,
)
from app.schemas.telemetry import TelemetryIngest
from app.services.live_state import AssetIdentity, live_state
from app.utils.time import hours_between, minutes_ago, utc_now


@dataclass(slots=True)
class ChannelStats:
    """Rolling statistics for one telemetry channel on one asset."""

    mean: float
    stddev: float
    minimum: float
    maximum: float
    samples: int

    def z_score(self, value: float) -> float:
        """Standard deviations between ``value`` and the window mean.

        Returns 0 when the window is effectively flat: dividing by a
        near-zero deviation would turn measurement noise into a large,
        meaningless score.
        """
        if self.stddev < 1e-6:
            return 0.0
        return (value - self.mean) / self.stddev


@dataclass(slots=True)
class AssetWindow:
    """Everything the layers know about one asset for this cycle."""

    identity: AssetIdentity
    latest: TelemetryIngest | None
    stats: dict[str, ChannelStats] = field(default_factory=dict)

    #: Health at the start and end of the window, for trend estimation.
    health_first: float | None = None
    health_last: float | None = None
    window_hours: float = 0.0

    #: Share of window samples in which the asset was actively running.
    running_ratio: float = 0.0
    #: Share of window samples the source considered trustworthy.
    good_quality_ratio: float = 1.0
    #: Mean power drawn while running, used by the OEE performance factor.
    mean_running_power_w: float = 0.0
    #: Mean commanded load while running, as a percentage of nameplate. This is
    #: what the asset was *asked* to draw, which is the only fair yardstick for
    #: what it actually drew.
    mean_load_percent: float = 0.0

    sample_count: int = 0
    #: Newest reading timestamp in the window. Connectivity is inferred from
    #: this rather than from a packet, because a device cannot announce that it
    #: has gone away.
    last_seen_at: datetime | None = None
    #: Energy accumulated across the window, from the difference between the
    #: first and last meter reading. A cumulative counter must only climb, so a
    #: negative delta is itself a fault signal.
    energy_delta_kwh: float | None = None

    open_alerts: int = 0
    critical_alerts: int = 0
    lifetime_failures: int = 0
    mean_repair_hours: float | None = None
    open_fault_keys: set[str] = field(default_factory=set)
    #: Open alert id per fault type, so the anomaly layer can close one when
    #: its underlying condition has cleared.
    open_alert_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    #: Currently-open anomaly id per fault type. An anomaly is one *occurrence*
    #: of a condition, not one detection cycle — without this a fault that
    #: persists for an hour would write a fresh row every fifteen seconds and
    #: bury the operator in duplicates of the same problem.
    open_anomaly_ids: dict[str, uuid.UUID] = field(default_factory=dict)

    @property
    def health_slope_per_hour(self) -> float:
        """Rate of health change, in points per hour.

        Negative means degrading. This is the signal Layer 2 turns into a
        remaining-useful-life estimate.
        """
        if (
            self.health_first is None
            or self.health_last is None
            or self.window_hours <= 0.01
        ):
            return 0.0
        return (self.health_last - self.health_first) / self.window_hours


@dataclass(slots=True)
class IntelligenceContext:
    """Inputs shared by every layer in one computation pass."""

    computed_at: datetime
    window_start: datetime
    window_minutes: int
    windows: dict[uuid.UUID, AssetWindow] = field(default_factory=dict)

    def assets(self) -> list[AssetWindow]:
        return list(self.windows.values())


#: Channels the statistical detector examines.
TRACKED_CHANNELS: tuple[str, ...] = (
    "voltage_v",
    "current_a",
    "power_w",
    "temperature_c",
    "power_factor",
    "frequency_hz",
)


async def build_context(session: AsyncSession) -> IntelligenceContext:
    """Gather one cycle's inputs for every asset."""
    now = utc_now()
    window_minutes = settings.intelligence_window_minutes
    window_start = minutes_ago(window_minutes, reference=now)

    context = IntelligenceContext(
        computed_at=now, window_start=window_start, window_minutes=window_minutes
    )

    identities = live_state.identities()
    if not identities:
        return context

    for identity in identities:
        context.windows[identity.id] = AssetWindow(
            identity=identity, latest=live_state.latest(identity.id)
        )

    await _load_channel_stats(session, context)
    await _load_window_shape(session, context)
    await _load_alert_history(session, context)
    await _load_open_anomalies(session, context)

    return context


async def _load_open_anomalies(
    session: AsyncSession, context: IntelligenceContext
) -> None:
    """Index anomalies that are still open, by asset and fault."""
    rows = (
        await session.execute(
            select(AnomalyResult.id, AnomalyResult.asset_id, AnomalyResult.fault_type)
            .where(AnomalyResult.status == AnomalyStatus.OPEN)
            .order_by(AnomalyResult.detected_at)
        )
    ).all()

    for anomaly_id, asset_id, fault_type in rows:
        window = context.windows.get(asset_id)
        if window is not None and fault_type is not None:
            window.open_anomaly_ids[str(fault_type)] = anomaly_id


async def _load_channel_stats(session: AsyncSession, context: IntelligenceContext) -> None:
    """Compute per-asset, per-channel statistics over the window."""
    columns = [
        getattr(Telemetry, channel) for channel in TRACKED_CHANNELS
    ]
    aggregates = []
    for column in columns:
        aggregates.extend(
            [
                func.avg(column),
                func.stddev_samp(column),
                func.min(column),
                func.max(column),
                func.count(column),
            ]
        )

    rows = (
        await session.execute(
            select(Telemetry.asset_id, *aggregates)
            .where(Telemetry.time >= context.window_start)
            .group_by(Telemetry.asset_id)
        )
    ).all()

    for row in rows:
        asset_id = row[0]
        window = context.windows.get(asset_id)
        if window is None:
            continue

        for index, channel in enumerate(TRACKED_CHANNELS):
            offset = 1 + index * 5
            mean, stddev, minimum, maximum, count = row[offset : offset + 5]
            if mean is None or not count:
                continue
            window.stats[channel] = ChannelStats(
                mean=float(mean),
                stddev=float(stddev or 0.0),
                minimum=float(minimum),
                maximum=float(maximum),
                samples=int(count),
            )


async def _load_window_shape(session: AsyncSession, context: IntelligenceContext) -> None:
    """Load health trend, duty ratio, data quality and running power.

    These feed the predictive slope and the OEE factors, and all four come from
    the same scan, so they are gathered together.
    """
    rows = (
        await session.execute(
            select(
                Telemetry.asset_id,
                func.count().label("samples"),
                func.min(Telemetry.time).label("first_time"),
                func.max(Telemetry.time).label("last_time"),
                func.count(Telemetry.id)
                .filter(Telemetry.operational_state == OperationalState.RUNNING)
                .label("running"),
                func.count(Telemetry.id)
                .filter(Telemetry.quality == DataQuality.GOOD)
                .label("good"),
                func.avg(Telemetry.power_w)
                .filter(Telemetry.operational_state == OperationalState.RUNNING)
                .label("running_power"),
                func.avg(Telemetry.load_percent)
                .filter(Telemetry.operational_state == OperationalState.RUNNING)
                .label("running_load"),
                func.max(Telemetry.energy_kwh).label("energy_max"),
                func.min(Telemetry.energy_kwh).label("energy_min"),
            )
            .where(Telemetry.time >= context.window_start)
            .group_by(Telemetry.asset_id)
        )
    ).all()

    for row in rows:
        window = context.windows.get(row.asset_id)
        if window is None or not row.samples:
            continue

        window.sample_count = int(row.samples)
        window.running_ratio = float(row.running or 0) / float(row.samples)
        window.good_quality_ratio = float(row.good or 0) / float(row.samples)
        window.mean_running_power_w = float(row.running_power or 0.0)
        window.mean_load_percent = float(row.running_load or 0.0)
        window.window_hours = hours_between(row.first_time, row.last_time)
        window.last_seen_at = row.last_time

        if row.energy_max is not None and row.energy_min is not None:
            window.energy_delta_kwh = float(row.energy_max) - float(row.energy_min)

    # Health at each end of the window. Two small ordered queries per asset
    # would be expensive across a fleet, so both ends come from one pass using
    # the aggregate over the sorted window.
    edge_rows = (
        await session.execute(
            select(
                Telemetry.asset_id,
                func.min(Telemetry.time),
                func.max(Telemetry.time),
            )
            .where(Telemetry.time >= context.window_start)
            .group_by(Telemetry.asset_id)
        )
    ).all()

    edges = {row[0]: (row[1], row[2]) for row in edge_rows}
    if not edges:
        return

    boundary_times = {t for pair in edges.values() for t in pair}
    health_rows = (
        await session.execute(
            select(Telemetry.asset_id, Telemetry.time, Telemetry.health_score).where(
                Telemetry.time.in_(boundary_times)
            )
        )
    ).all()

    health_by_asset: dict[uuid.UUID, dict[datetime, float]] = {}
    for asset_id, moment, score in health_rows:
        if score is None:
            continue
        health_by_asset.setdefault(asset_id, {})[moment] = float(score)

    for asset_id, (first_time, last_time) in edges.items():
        window = context.windows.get(asset_id)
        readings = health_by_asset.get(asset_id)
        if window is None or not readings:
            continue
        window.health_first = readings.get(first_time)
        window.health_last = readings.get(last_time)


async def _load_alert_history(session: AsyncSession, context: IntelligenceContext) -> None:
    """Load open alert counts and repair history.

    Repair duration is the interval between an alert being raised and resolved,
    which is exactly what MTTR measures.
    """
    open_rows = (
        await session.execute(
            select(
                Alert.asset_id,
                func.count(),
                func.count(Alert.id).filter(Alert.severity == "critical"),
            )
            .where(Alert.status.in_((AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED)))
            .group_by(Alert.asset_id)
        )
    ).all()

    for asset_id, total, critical in open_rows:
        window = context.windows.get(asset_id)
        if window is not None:
            window.open_alerts = int(total)
            window.critical_alerts = int(critical or 0)

    fault_rows = (
        await session.execute(
            select(Alert.id, Alert.asset_id, Alert.fault_type).where(
                Alert.status.in_((AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED))
            )
        )
    ).all()
    for alert_id, asset_id, fault_type in fault_rows:
        window = context.windows.get(asset_id)
        if window is not None and fault_type is not None:
            key = str(fault_type)
            window.open_fault_keys.add(key)
            window.open_alert_ids[key] = alert_id

    failure_rows = (
        await session.execute(
            select(
                Alert.asset_id,
                func.count(),
                func.avg(
                    func.extract("epoch", Alert.resolved_at - Alert.triggered_at) / 3600.0
                ),
            )
            .where(Alert.severity == "critical")
            .group_by(Alert.asset_id)
        )
    ).all()

    for asset_id, count, mean_hours in failure_rows:
        window = context.windows.get(asset_id)
        if window is None:
            continue
        window.lifetime_failures = int(count or 0)
        window.mean_repair_hours = float(mean_hours) if mean_hours is not None else None

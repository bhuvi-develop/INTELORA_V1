"""Dashboard schemas.

These are page-shaped rather than resource-shaped. The Cockpit is served by a
few aggregate payloads instead of composing a dozen resource calls, which is
what makes the five-second comprehension target achievable over a real network.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.alert import AlertSummary
from app.schemas.asset import AssetTypeSummary
from app.schemas.enums import AssetType, HealthState
from app.schemas.intelligence import IntelligenceSummary
from app.schemas.telemetry import ChartSeries


class KpiValue(BaseModel):
    """One executive KPI.

    ``target`` carries the route the card navigates to. Making every KPI an
    entry point is a product requirement, and putting the destination in the
    payload keeps the mapping in one place rather than hardcoded in the view.
    """

    key: str
    label: str
    value: float | None = None
    unit: str | None = None
    precision: int = 0
    delta: float | None = None
    delta_label: str | None = None
    tone: str = "neutral"
    target: str | None = None
    caption: str | None = None


class SystemStatus(BaseModel):
    """The single dominant verdict at the top of the Cockpit.

    One sentence a user can read in under five seconds, backed by the counts
    that justify it.
    """

    state: HealthState
    headline: str
    detail: str
    assets_total: int = 0
    assets_online: int = 0
    active_alerts: int = 0
    critical_alerts: int = 0
    live: bool = False
    generated_at: datetime


class ActivityItem(BaseModel):
    """One entry in the Cockpit live feed.

    A human-readable event stream — distinct from the raw telemetry table,
    which lives on the module pages.
    """

    id: str
    kind: str
    severity: str
    title: str
    detail: str
    asset_id: uuid.UUID | None = None
    asset_code: str | None = None
    occurred_at: datetime


class EnergySummary(BaseModel):
    """Energy and its business translation.

    ``coverage`` reports the share of the fleet that actually meters energy —
    mobile chargers do not, and a total presented without that caveat would
    overstate confidence.
    """

    today_kwh: float = 0.0
    today_cost: float = 0.0
    today_saving: float = 0.0
    lifetime_kwh: float = 0.0
    live_power_w: float = 0.0
    currency: str = "USD"
    tariff_per_kwh: float = 0.0
    metered_assets: int = 0
    total_assets: int = 0
    coverage: float = 0.0


class CockpitOverview(BaseModel):
    """The complete Mission Control payload.

    Assembled once by the Business Intelligence Layer and delivered in a single
    response, then kept current by the WebSocket stream.
    """

    organization: str
    generated_at: datetime
    system_status: SystemStatus
    kpis: list[KpiValue] = Field(default_factory=list)
    asset_types: list[AssetTypeSummary] = Field(default_factory=list)
    intelligence: IntelligenceSummary = Field(default_factory=IntelligenceSummary)
    energy: EnergySummary = Field(default_factory=EnergySummary)
    alerts: AlertSummary = Field(default_factory=AlertSummary)
    activity: list[ActivityItem] = Field(default_factory=list)


class DistributionSlice(BaseModel):
    """A labelled proportion, for donut and bar charts."""

    key: str
    label: str
    value: float
    tone: str = "neutral"


class ChartBundle(BaseModel):
    """Every Cockpit chart in one payload.

    Delivered together so the charts resolve as a single coordinated wave
    rather than twelve independent loading states.
    """

    generated_at: datetime
    window_minutes: int
    energy: ChartSeries
    power: ChartSeries
    voltage: ChartSeries
    current: ChartSeries
    temperature: ChartSeries
    power_factor: ChartSeries
    health: ChartSeries
    health_distribution: list[DistributionSlice] = Field(default_factory=list)
    type_distribution: list[DistributionSlice] = Field(default_factory=list)


class LiveTick(BaseModel):
    """The per-second delta pushed over the WebSocket.

    Only what changes: the full overview is fetched once over REST, then this
    keeps it current without re-sending static identity.
    """

    generated_at: datetime
    system_status: SystemStatus
    kpis: list[KpiValue] = Field(default_factory=list)
    asset_types: list[AssetTypeSummary] = Field(default_factory=list)
    energy: EnergySummary
    live_power_w: float = 0.0
    fleet_health: float = 0.0
    samples_ingested: int = 0


class RecentTelemetryRow(BaseModel):
    """One row of the recent-telemetry table on the module pages."""

    time: datetime
    asset_id: uuid.UUID
    asset_code: str
    asset_name: str
    asset_type: AssetType
    voltage_v: float | None = None
    current_a: float | None = None
    power_w: float | None = None
    energy_kwh: float | None = None
    temperature_c: float | None = None
    frequency_hz: float | None = None
    power_factor: float | None = None
    health_score: float | None = None
    health_state: HealthState | None = None
    quality: str = "good"

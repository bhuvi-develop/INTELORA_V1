"""Asset schemas, including the unified business model.

Two models, deliberately distinct:

* :class:`AssetRead` and the telemetry schemas describe what a device actually
  reports, which differs by asset type.
* :class:`AssetBusinessModel` is identical for every asset type and is what
  dashboard surfaces bind to. A new asset category integrates by satisfying
  this contract; absent values are ``None`` and degrade gracefully rather than
  breaking layout.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import (
    AssetType,
    ConnectivityState,
    HealthState,
    LifecycleStage,
    OperationalState,
)


class AssetCapabilities(BaseModel):
    """Which telemetry channels an asset type reports.

    Drives conditional rendering in the UI. The frontend reads capabilities
    rather than branching on asset type, so adding a category requires no
    presentation change.
    """

    # Electrical
    voltage: bool = True
    current: bool = True
    power: bool = True
    reactive_power: bool = False
    apparent_power: bool = False
    energy: bool = False
    frequency: bool = False
    power_factor: bool = False
    temperature: bool = True

    # Operating context — every category reports these.
    runtime: bool = True
    load: bool = True

    # Asset-specific
    relay: bool = False
    battery: bool = False
    charge_cycles: bool = False
    fast_charging: bool = False
    indoor_temperature: bool = False


class AssetScope(BaseModel):
    """Where an asset sits in the organisation hierarchy."""

    organization_id: uuid.UUID
    organization_name: str | None = None
    location_id: uuid.UUID | None = None
    location_name: str | None = None
    building: str | None = None
    department: str | None = None
    asset_group_id: uuid.UUID | None = None
    asset_group_name: str | None = None


class AssetRead(BaseModel):
    """Full asset identity and current state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_code: str
    name: str
    asset_type: AssetType
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None

    rated_power_w: float
    rated_voltage_v: float
    commissioned_at: datetime | None = None

    health_score: float
    health_state: HealthState
    operational_state: OperationalState
    connectivity_state: ConnectivityState
    lifecycle_stage: LifecycleStage

    last_seen_at: datetime | None = None
    operating_hours: float
    lifetime_energy_kwh: float
    relay_operations: int

    scope: AssetScope | None = None
    capabilities: AssetCapabilities | None = None


class AssetBusinessModel(BaseModel):
    """The unified contract every asset exposes, whatever its type.

    Fields are optional where a device may not report them — a mobile charger
    has no energy channel. Consumers must render absence as "not reported",
    never as zero, or fleet averages become quietly wrong.
    """

    asset_id: uuid.UUID
    asset_code: str
    name: str
    asset_type: AssetType

    # Condition — always present.
    health_score: float
    health_state: HealthState
    operational_state: OperationalState
    connectivity_state: ConnectivityState

    # Measured — present where the asset type reports them.
    power_w: float | None = None
    temperature_c: float | None = None
    energy_kwh: float | None = None

    # Business Intelligence Layer outputs — never telemetry.
    cost: float = 0.0
    efficiency: float = 0.0
    business_score: float = 0.0

    active_alerts: int = 0
    last_seen_at: datetime | None = None


class AssetTypeSummary(BaseModel):
    """Fleet roll-up for one asset category.

    Backs the three premium cards in Cockpit section 3.
    """

    asset_type: AssetType
    label: str
    total: int = 0
    healthy: int = 0
    warning: int = 0
    critical: int = 0
    online: int = 0

    average_health: float = 0.0
    total_power_w: float | None = None
    average_temperature_c: float | None = None
    total_energy_kwh: float | None = None
    efficiency: float = 0.0
    active_alerts: int = 0

    capabilities: AssetCapabilities
    trend: list[float] = Field(default_factory=list)


class AssetCreate(BaseModel):
    """Payload for commissioning a new asset."""

    asset_code: str = Field(min_length=2, max_length=48)
    name: str = Field(min_length=1, max_length=160)
    asset_type: AssetType
    organization_id: uuid.UUID
    location_id: uuid.UUID | None = None
    asset_group_id: uuid.UUID | None = None
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    rated_power_w: float = Field(default=0.0, ge=0)
    rated_voltage_v: float = Field(default=230.0, gt=0)
    commissioned_at: datetime | None = None


class AssetUpdate(BaseModel):
    """Partial update. Unset fields are left untouched."""

    name: str | None = Field(default=None, min_length=1, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    location_id: uuid.UUID | None = None
    asset_group_id: uuid.UUID | None = None
    rated_power_w: float | None = Field(default=None, ge=0)
    rated_voltage_v: float | None = Field(default=None, gt=0)
    operational_state: OperationalState | None = None
    lifecycle_stage: LifecycleStage | None = None

"""Telemetry schemas.

``TelemetryIngest`` is the contract every data source satisfies — the Digital
Twin Engine, the future MQTT bridge, and the REST ingestion endpoint all
produce this same shape. That is what allows the platform to swap sources
without the dashboard ever knowing which one is attached.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import (
    AssetType,
    ChargingState,
    ConnectivityState,
    DataQuality,
    HealthState,
    OperationalState,
    TelemetrySource,
)


class TelemetryIngest(BaseModel):
    """A single reading entering the Telemetry Layer.

    Every channel is optional because asset types genuinely differ; validation
    of which channels are *expected* belongs to the asset's capability profile,
    not to this envelope.
    """

    asset_id: uuid.UUID
    time: datetime

    voltage_v: float | None = None
    current_a: float | None = None
    power_w: float | None = None
    reactive_power_var: float | None = None
    apparent_power_va: float | None = None
    energy_kwh: float | None = None
    frequency_hz: float | None = None
    power_factor: float | None = Field(default=None, ge=0, le=1)
    temperature_c: float | None = None

    # --- Operating context, common to every asset type -----------------------
    runtime_hours: float | None = Field(default=None, ge=0)
    load_percent: float | None = Field(default=None, ge=0, le=200)

    # --- Actuation state (observed, never commanded) -------------------------
    relay_status: bool | None = None
    relay_operations: int | None = Field(default=None, ge=0)

    # --- Asset-specific channels ----------------------------------------------
    charging_state: ChargingState | None = None
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    charge_cycles: int | None = Field(default=None, ge=0)
    fast_charging: bool | None = None
    indoor_temperature_c: float | None = None

    # --- Derived condition ----------------------------------------------------
    # Left unset by data sources. The Health Engine fills these in during
    # normalisation, from the electrical channels above. A source that asserts
    # its own health is asserting a conclusion the platform exists to reach.
    health_score: float | None = Field(default=None, ge=0, le=100)
    health_state: HealthState | None = None

    operational_state: OperationalState | None = None
    connectivity_state: ConnectivityState | None = None

    source: TelemetrySource = TelemetrySource.DIGITAL_TWIN
    quality: DataQuality = DataQuality.GOOD


class TelemetryRead(TelemetryIngest):
    """A stored reading, enriched with asset identity for table display."""

    model_config = ConfigDict(from_attributes=True)

    asset_code: str | None = None
    asset_name: str | None = None
    asset_type: AssetType | None = None


class SeriesPoint(BaseModel):
    """One point on a trend line."""

    t: datetime
    v: float | None = None


class ChartSeries(BaseModel):
    """A named, unit-bearing series ready for ECharts.

    Units travel with the data so that axis labels and tooltips cannot drift
    out of sync with what is actually plotted.
    """

    key: str
    label: str
    unit: str
    points: list[SeriesPoint] = Field(default_factory=list)


class TelemetryQuery(BaseModel):
    """Explicit bounds for a history request.

    Retention is unlimited, so an unbounded query is never permitted.
    """

    asset_id: uuid.UUID | None = None
    asset_type: AssetType | None = None
    start: datetime
    end: datetime
    max_points: int = Field(default=240, ge=2, le=2000)

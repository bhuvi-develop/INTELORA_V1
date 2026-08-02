"""Raw telemetry — the platform's time-series table.

Backed by a TimescaleDB hypertable partitioned on ``time``. The primary key is
composite ``(time, id)`` because Timescale requires the partitioning column to
participate in every unique constraint.

Columns are deliberately nullable: the three supported asset types report
genuinely different channels, and a mobile charger that reports no frequency,
power factor or energy must not be forced to store zeros that would then be
averaged into fleet statistics as if they were measurements.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base
from app.database.types import enum_column
from app.schemas.enums import (
    ChargingState,
    ConnectivityState,
    DataQuality,
    HealthState,
    OperationalState,
    TelemetrySource,
)


class Telemetry(Base):
    """One reading from one asset at one instant."""

    __tablename__ = "telemetry"
    __table_args__ = (
        # Primary access pattern: "the last N readings for this asset".
        Index("ix_telemetry_asset_time", "asset_id", "time"),
        # Secondary: fleet-wide sweeps by the intelligence layers.
        Index("ix_telemetry_time_desc", "time"),
    )

    # --- Identity ------------------------------------------------------------
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )

    # --- Electrical channels -------------------------------------------------
    voltage_v: Mapped[float | None] = mapped_column(Float)
    current_a: Mapped[float | None] = mapped_column(Float)

    # Single-figure power for chargers; for air conditioners this carries
    # active power and the reactive/apparent columns are populated too.
    power_w: Mapped[float | None] = mapped_column(Float)
    reactive_power_var: Mapped[float | None] = mapped_column(Float)
    apparent_power_va: Mapped[float | None] = mapped_column(Float)

    energy_kwh: Mapped[float | None] = mapped_column(Float)
    frequency_hz: Mapped[float | None] = mapped_column(Float)
    power_factor: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)

    # --- Operating context ----------------------------------------------------
    # Common to every asset type. Runtime is the device's own cumulative
    # powered-on hours; load is draw as a share of nameplate. Both are part of
    # the common contract because every category can report them, and both are
    # inputs the OEE performance factor depends on.
    runtime_hours: Mapped[float | None] = mapped_column(Float)
    load_percent: Mapped[float | None] = mapped_column(Float)

    # --- Actuation state (observed, never commanded) -------------------------
    relay_status: Mapped[bool | None] = mapped_column(Boolean)
    relay_operations: Mapped[int | None] = mapped_column(Integer)

    # --- Asset-specific channels ----------------------------------------------
    # Nullable and sparse by design: a category that does not charge a battery
    # stores NULL here rather than a zero that would be averaged into fleet
    # statistics as though it were a measurement.
    charging_state: Mapped[ChargingState | None] = mapped_column(
        enum_column(ChargingState)
    )
    battery_percent: Mapped[float | None] = mapped_column(Float)
    charge_cycles: Mapped[int | None] = mapped_column(Integer)
    fast_charging: Mapped[bool | None] = mapped_column(Boolean)

    #: Conditioned-space temperature, distinct from the device's own case
    #: temperature in ``temperature_c``.
    indoor_temperature_c: Mapped[float | None] = mapped_column(Float)

    # --- Derived condition ---------------------------------------------------
    health_score: Mapped[float | None] = mapped_column(Float)
    health_state: Mapped[HealthState | None] = mapped_column(enum_column(HealthState))
    operational_state: Mapped[OperationalState | None] = mapped_column(
        enum_column(OperationalState)
    )
    connectivity_state: Mapped[ConnectivityState | None] = mapped_column(
        enum_column(ConnectivityState)
    )

    # --- Provenance ----------------------------------------------------------
    source: Mapped[TelemetrySource] = mapped_column(
        enum_column(TelemetrySource), nullable=False, default=TelemetrySource.DIGITAL_TWIN
    )
    quality: Mapped[DataQuality] = mapped_column(
        enum_column(DataQuality), nullable=False, default=DataQuality.GOOD
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<Telemetry {self.asset_id} @ {self.time}>"

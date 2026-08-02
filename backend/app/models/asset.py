"""The asset identity table.

One row per physical (or virtual) device. Every telemetry record, AI result and
alert in the platform hangs off this table — it is the "one identity per asset"
the SSOT requires.

The three status columns are the denormalised *current* state, maintained by
the telemetry service on ingest so that fleet-wide queries do not have to scan
the hypertable. History lives in ``telemetry``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import enum_column
from app.schemas.enums import (
    AssetType,
    ConnectivityState,
    HealthState,
    LifecycleStage,
    OperationalState,
)

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.organization import AssetGroup, Location, Organization


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A monitored device."""

    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_org_type", "organization_id", "asset_type"),
        Index("ix_assets_org_health", "organization_id", "health_state"),
    )

    # --- Identity ------------------------------------------------------------
    asset_code: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(enum_column(AssetType), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    serial_number: Mapped[str | None] = mapped_column(String(120))

    # --- Scope ---------------------------------------------------------------
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    asset_group_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset_groups.id", ondelete="SET NULL"), index=True
    )

    # --- Nameplate -----------------------------------------------------------
    rated_power_w: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rated_voltage_v: Mapped[float] = mapped_column(Float, nullable=False, default=230.0)
    commissioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Current state (three independent dimensions) ------------------------
    health_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    health_state: Mapped[HealthState] = mapped_column(
        enum_column(HealthState), nullable=False, default=HealthState.HEALTHY, index=True
    )
    operational_state: Mapped[OperationalState] = mapped_column(
        enum_column(OperationalState), nullable=False, default=OperationalState.IDLE, index=True
    )
    connectivity_state: Mapped[ConnectivityState] = mapped_column(
        enum_column(ConnectivityState),
        nullable=False,
        default=ConnectivityState.UNKNOWN,
        index=True,
    )
    lifecycle_stage: Mapped[LifecycleStage] = mapped_column(
        enum_column(LifecycleStage), nullable=False, default=LifecycleStage.NORMAL
    )

    # --- Running counters ----------------------------------------------------
    # Maintained on ingest; cheaper than aggregating the hypertable for every
    # Cockpit request, and the values are monotonic so they cannot drift.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    operating_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lifetime_energy_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    relay_operations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Relationships -------------------------------------------------------
    organization: Mapped[Organization] = relationship(back_populates="assets")
    location: Mapped[Location | None] = relationship(back_populates="assets")
    asset_group: Mapped[AssetGroup | None] = relationship(back_populates="assets")
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<Asset {self.asset_code} {self.asset_type}>"

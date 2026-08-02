"""Intelligence Layer result tables.

One table per layer. The SSOT is explicit that no layer overwrites another's
work, so each writes only its own table and reads its inputs from the layers
below it. Results are append-only: a new computation inserts a new row rather
than updating the previous one, which preserves the audit trail an enterprise
platform needs.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.types import enum_column
from app.schemas.enums import (
    AlertSeverity,
    AnomalyStatus,
    AssetType,
    BusinessImpact,
    FaultType,
    LifecycleStage,
    RecommendedAction,
    RiskLevel,
    RootCause,
    ScopeType,
)


class AnomalyResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Layer 1 — a detected deviation from expected behaviour."""

    __tablename__ = "anomaly_results"
    __table_args__ = (Index("ix_anomaly_asset_detected", "asset_id", "detected_at"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )

    # References the telemetry window that produced this result, completing the
    # telemetry → result → alert integrity chain.
    telemetry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    channel: Mapped[str] = mapped_column(String(48), nullable=False)
    fault_type: Mapped[FaultType] = mapped_column(enum_column(FaultType), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(enum_column(AlertSeverity), nullable=False)

    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    observed_value: Mapped[float | None] = mapped_column(Float)
    expected_min: Mapped[float | None] = mapped_column(Float)
    expected_max: Mapped[float | None] = mapped_column(Float)
    deviation_sigma: Mapped[float | None] = mapped_column(Float)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Diagnosis -------------------------------------------------------------
    # The fault type records what was seen; these record why it happened and
    # what to do. Stored on the result rather than derived on read, so the
    # diagnosis reflects the conditions at detection time — re-deriving it later
    # against a recovered asset would produce a different, wrong answer.
    root_cause: Mapped[RootCause] = mapped_column(
        enum_column(RootCause), nullable=False, default=RootCause.UNDETERMINED, index=True
    )
    recommendation: Mapped[str | None] = mapped_column(Text)

    # --- Lifecycle -------------------------------------------------------------
    # Distinct from alert lifecycle: an anomaly is an observation that clears on
    # its own when the condition passes. Most never become alerts.
    status: Mapped[AnomalyStatus] = mapped_column(
        enum_column(AnomalyStatus), nullable=False, default=AnomalyStatus.OPEN, index=True
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PredictiveResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Layer 2 — forward-looking failure estimate."""

    __tablename__ = "predictive_results"
    __table_args__ = (Index("ix_predictive_asset_computed", "asset_id", "computed_at"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    failure_probability: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_useful_life_hours: Mapped[float | None] = mapped_column(Float)
    predicted_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(
        enum_column(RiskLevel), nullable=False, index=True
    )

    degradation_rate_per_hour: Mapped[float | None] = mapped_column(Float)
    dominant_fault_type: Mapped[FaultType | None] = mapped_column(enum_column(FaultType))
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Component detail --------------------------------------------------------
    # A single score says whether to worry; this says where to look. Stored as
    # JSON because the component set differs by asset category and adding a
    # category must not require a migration.
    component_health: Mapped[list | None] = mapped_column(JSON)
    #: The subsystem most likely to take the asset down first.
    weakest_component: Mapped[str | None] = mapped_column(String(48))
    weakest_component_score: Mapped[float | None] = mapped_column(Float)

    #: Recommended service window, mirrored from the preventive layer so a
    #: prediction is actionable without a second lookup.
    maintenance_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    maintenance_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class PreventiveResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Layer 3 — scheduled maintenance recommendation.

    Has no page of its own; surfaces on the Predictive and APM screens.
    """

    __tablename__ = "preventive_results"
    __table_args__ = (Index("ix_preventive_asset_computed", "asset_id", "computed_at"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    maintenance_due: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[RiskLevel] = mapped_column(enum_column(RiskLevel), nullable=False)

    task: Mapped[str] = mapped_column(String(200), nullable=False)
    interval_hours: Mapped[float | None] = mapped_column(Float)
    hours_since_service: Mapped[float | None] = mapped_column(Float)

    # --- Work definition ---------------------------------------------------------
    # The single task string above is the headline; this is the work itself.
    # JSON because the checklist is generated from the asset's current condition
    # and its length varies per plan.
    tasks: Mapped[list | None] = mapped_column(JSON)
    checklist: Mapped[list | None] = mapped_column(JSON)
    estimated_duration_hours: Mapped[float | None] = mapped_column(Float)

    #: When to prompt someone, ahead of the window opening.
    reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    #: Which subsystem triggered the plan, when condition rather than interval
    #: drove it.
    triggered_by_component: Mapped[str | None] = mapped_column(String(48))


class PrescriptiveResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Layer 4 — the recommended course of action.

    Advisory only. The source of the Cockpit's *Today's cost saving* figure.
    """

    __tablename__ = "prescriptive_results"
    __table_args__ = (Index("ix_prescriptive_asset_computed", "asset_id", "computed_at"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    recommended_action: Mapped[RecommendedAction] = mapped_column(
        enum_column(RecommendedAction), nullable=False, index=True
    )
    advice: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[RiskLevel] = mapped_column(enum_column(RiskLevel), nullable=False)

    energy_saving_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_saving: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # --- Value of acting ---------------------------------------------------------
    # Savings alone do not rank a recommendation: avoiding ten dollars on an
    # asset about to fail outranks saving fifty on one that is fine. Impact
    # blends the money with the consequence of inaction.
    business_impact: Mapped[BusinessImpact] = mapped_column(
        enum_column(BusinessImpact),
        nullable=False,
        default=BusinessImpact.LOW,
        index=True,
    )
    #: Health points the asset is expected to recover if the action is taken.
    expected_health_gain: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    #: Which subsystem the action addresses.
    target_component: Mapped[str | None] = mapped_column(String(48))
    #: Plain-language statement of what happens if nothing is done.
    impact_statement: Mapped[str | None] = mapped_column(Text)


class ApmResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Layer 5 — reliability engineering and business value.

    The two families of output are kept together in storage but separated in
    presentation, which is where principle 4's device/business split lives.
    """

    __tablename__ = "apm_results"
    __table_args__ = (Index("ix_apm_asset_computed", "asset_id", "computed_at"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # --- Reliability engineering --------------------------------------------
    health_index: Mapped[float] = mapped_column(Float, nullable=False)
    mtbf_hours: Mapped[float | None] = mapped_column(Float)
    mttr_hours: Mapped[float | None] = mapped_column(Float)
    availability: Mapped[float] = mapped_column(Float, nullable=False)
    reliability: Mapped[float] = mapped_column(Float, nullable=False)
    maintainability: Mapped[float] = mapped_column(Float, nullable=False)
    criticality: Mapped[RiskLevel] = mapped_column(enum_column(RiskLevel), nullable=False)
    lifecycle_stage: Mapped[LifecycleStage] = mapped_column(
        enum_column(LifecycleStage), nullable=False
    )
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Share of the window the asset was actually working. Distinct from
    #: availability: an asset can be perfectly available and barely used, and
    #: conflating the two hides the entire class of over-provisioned equipment.
    utilization: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    #: Remaining service life as a 0–100 score. The stage above answers "which
    #: band", this answers "how far through", which is what ranks two assets
    #: sitting in the same band.
    lifecycle_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)

    # --- Business ------------------------------------------------------------
    cost_exposure: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    maintenance_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    #: Cost of the energy this asset consumed over the window, priced at the
    #: configured tariff. Kept separate from maintenance cost because they are
    #: different budgets answering to different people.
    energy_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    maintenance_roi: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    business_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    #: How much the business should care, blending exposure with criticality.
    #: Shares the scale used by the prescriptive layer so the two rank together.
    business_impact: Mapped[BusinessImpact] = mapped_column(
        enum_column(BusinessImpact),
        nullable=False,
        default=BusinessImpact.LOW,
        index=True,
    )
    repair_or_replace: Mapped[str] = mapped_column(String(24), nullable=False, default="repair")
    rank: Mapped[int | None] = mapped_column(Integer)
    #: Position within this asset's own group, and within its category. A
    #: fleet-wide rank alone is not actionable for a manager who owns one
    #: fleet: a charger can be 90th overall and still the worst charger there is.
    fleet_rank: Mapped[int | None] = mapped_column(Integer)
    type_rank: Mapped[int | None] = mapped_column(Integer)

    # --- Trends ----------------------------------------------------------------
    # Deltas against the previous computation. Stored rather than derived on
    # read because the comparison must be against the cycle that actually
    # preceded this one; re-deriving later against whatever rows survive
    # retention would silently change the answer.
    health_trend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    failure_trend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    maintenance_trend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    utilization_trend: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class OeeResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Layer 6 — operational efficiency at an aggregation scope.

    ``scope_id`` is nullable so that the enterprise-wide roll-up, which belongs
    to no single entity, can be stored in the same table.
    """

    __tablename__ = "oee_results"
    __table_args__ = (Index("ix_oee_scope_computed", "scope_type", "scope_id", "computed_at"),)

    scope_type: Mapped[ScopeType] = mapped_column(
        enum_column(ScopeType), nullable=False, index=True
    )
    scope_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), index=True)
    scope_label: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_type: Mapped[AssetType | None] = mapped_column(enum_column(AssetType))

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    availability: Mapped[float] = mapped_column(Float, nullable=False)
    performance: Mapped[float] = mapped_column(Float, nullable=False)
    quality: Mapped[float] = mapped_column(Float, nullable=False)
    oee: Mapped[float] = mapped_column(Float, nullable=False)
    asset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OeeAssetResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Layer 6 — OEE for one individual asset.

    Separate from :class:`OeeResult` rather than another ``scope_type`` on it.
    The two are genuinely different shapes: a scope row is identified by a
    label and an optional entity id, while this is identified by a foreign key
    to a specific asset and must cascade when that asset is removed. Folding
    the per-asset case into the scope table would mean a nullable foreign key
    that is meaningful for exactly one scope value, and every asset query would
    carry a scope filter that only ever has one answer.

    Write volume also differs by two orders of magnitude — one row per asset
    per cycle against a dozen scope rows — so the per-asset case earns its own
    index rather than competing with the rollups for one.
    """

    __tablename__ = "oee_asset_results"
    __table_args__ = (Index("ix_oee_asset_computed", "asset_id", "computed_at"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    availability: Mapped[float] = mapped_column(Float, nullable=False)
    performance: Mapped[float] = mapped_column(Float, nullable=False)
    quality: Mapped[float] = mapped_column(Float, nullable=False)
    oee: Mapped[float] = mapped_column(Float, nullable=False)

    #: Position within the whole estate and within this asset's own category,
    #: by OEE. Ranking at write time keeps the ordering consistent with the
    #: factors it was derived from.
    rank: Mapped[int | None] = mapped_column(Integer)
    type_rank: Mapped[int | None] = mapped_column(Integer)

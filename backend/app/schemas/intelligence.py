"""Intelligence Layer schemas — one group per layer, plus headline summaries.

Every layer's output carries a confidence figure and a human-readable
rationale. That pairing is what lets the platform satisfy principle 2: explain
what happened, why, what will happen, and what to do about it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import (
    AlertSeverity,
    AnomalyStatus,
    AssetType,
    BusinessImpact,
    FaultType,
    LifecycleStage,
    MaintenanceOutcome,
    MaintenanceTaskType,
    RecommendedAction,
    RiskLevel,
    RootCause,
    ScopeType,
)


class _AssetStamped(BaseModel):
    """Common asset identity carried by every intelligence result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    asset_code: str | None = None
    asset_name: str | None = None
    asset_type: AssetType | None = None


# --- Layer 1: Anomaly Detection ----------------------------------------------


class AnomalyRead(_AssetStamped):
    """A detected deviation, with its diagnosis."""

    detected_at: datetime
    telemetry_time: datetime
    channel: str
    fault_type: FaultType
    severity: AlertSeverity
    anomaly_score: float
    confidence: float
    observed_value: float | None = None
    expected_min: float | None = None
    expected_max: float | None = None
    deviation_sigma: float | None = None
    description: str

    #: Why it happened, and what to do — the difference between reporting a
    #: symptom and delivering intelligence.
    root_cause: RootCause = RootCause.UNDETERMINED
    recommendation: str | None = None

    status: AnomalyStatus = AnomalyStatus.OPEN
    cleared_at: datetime | None = None


class AnomalySummary(BaseModel):
    """Headline figures for the Anomaly module and Cockpit tile."""

    today: int = 0
    critical: int = 0
    warning: int = 0
    information: int = 0
    resolved_today: int = 0
    affected_assets: int = 0
    top_fault_type: FaultType | None = None
    average_confidence: float = 0.0

    #: Currently unresolved. Distinct from `today` — an anomaly raised
    #: yesterday and still present is open but not new.
    open_now: int = 0
    cleared_today: int = 0
    #: Most frequently diagnosed origin, which is what tells an operations lead
    #: whether they have one systemic problem or many unrelated ones.
    top_root_cause: RootCause | None = None


class FaultBreakdown(BaseModel):
    """Anomaly count for one fault type, for distribution views."""

    fault_type: FaultType
    label: str
    count: int
    critical: int = 0
    warning: int = 0


class RootCauseBreakdown(BaseModel):
    """Anomaly count for one diagnosed cause."""

    root_cause: RootCause
    label: str
    count: int
    affected_assets: int = 0


# --- Layer 2: Predictive Maintenance ------------------------------------------


class ComponentHealthRead(BaseModel):
    """Condition of one replaceable subsystem."""

    key: str
    label: str
    score: float
    weight: float
    basis: str
    degraded: bool = False


class PredictiveRead(_AssetStamped):
    """A forward-looking failure estimate, broken down by subsystem."""

    computed_at: datetime
    failure_probability: float
    remaining_useful_life_hours: float | None = None
    predicted_failure_at: datetime | None = None
    confidence: float
    risk_level: RiskLevel
    degradation_rate_per_hour: float | None = None
    dominant_fault_type: FaultType | None = None
    rationale: str

    #: Where to look, not merely how worried to be.
    component_health: list[ComponentHealthRead] = Field(default_factory=list)
    weakest_component: str | None = None
    weakest_component_score: float | None = None

    maintenance_window_start: datetime | None = None
    maintenance_window_end: datetime | None = None


class PredictiveSummary(BaseModel):
    """Headline figures for the Predictive module and Cockpit tile."""

    assets_at_risk: int = 0
    severe: int = 0
    high: int = 0
    average_failure_probability: float = 0.0
    shortest_rul_hours: float | None = None
    next_predicted_failure_at: datetime | None = None
    average_confidence: float = 0.0


# --- Layer 3: Preventive Maintenance ------------------------------------------


class MaintenanceTaskRead(BaseModel):
    """One item of work within a maintenance plan."""

    type: MaintenanceTaskType
    description: str
    estimated_hours: float
    #: True when the item was added because a subsystem is degraded, rather
    #: than because the service interval came round.
    condition_based: bool = False


class ChecklistItem(BaseModel):
    """A single step a technician ticks off."""

    step: int
    description: str
    complete: bool = False


class PreventiveRead(_AssetStamped):
    """A maintenance plan. Surfaces inside Predictive and APM."""

    computed_at: datetime
    maintenance_due: bool
    due_at: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    priority: RiskLevel
    task: str
    interval_hours: float | None = None
    hours_since_service: float | None = None

    #: The work itself, rather than a one-line summary of it.
    tasks: list[MaintenanceTaskRead] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    estimated_duration_hours: float | None = None
    reminder_at: datetime | None = None
    triggered_by_component: str | None = None


class MaintenanceLogRead(_AssetStamped):
    """One maintenance activity, planned or performed."""

    task_type: MaintenanceTaskType
    title: str
    description: str | None = None
    priority: RiskLevel
    outcome: MaintenanceOutcome

    scheduled_for: datetime | None = None
    window_end: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_hours: float | None = None

    checklist: list[ChecklistItem] = Field(default_factory=list)
    performed_by: str | None = None
    notes: str | None = None
    cost: float | None = None

    health_before: float | None = None
    health_after: float | None = None
    #: Points recovered, when both readings are present. This is how the value
    #: of maintenance becomes measurable instead of assumed.
    health_gain: float | None = None


class MaintenanceCalendarDay(BaseModel):
    """Scheduled work for a single day."""

    date: date
    total: int = 0
    severe: int = 0
    high: int = 0
    estimated_hours: float = 0.0
    entries: list[MaintenanceLogRead] = Field(default_factory=list)


class MaintenanceCalendar(BaseModel):
    """A window of scheduled work, grouped by day."""

    start: date
    end: date
    days: list[MaintenanceCalendarDay] = Field(default_factory=list)
    total_scheduled: int = 0
    total_estimated_hours: float = 0.0


class MaintenanceHistorySummary(BaseModel):
    """What has actually been done, as opposed to planned."""

    completed: int = 0
    scheduled: int = 0
    in_progress: int = 0
    deferred: int = 0
    total_cost: float = 0.0
    mean_duration_hours: float | None = None
    #: Mean health recovered per completed job — the return on the work.
    mean_health_gain: float | None = None


class PreventiveSummary(BaseModel):
    """Answers the Cockpit question "which devices require maintenance?"."""

    due_now: int = 0
    due_this_week: int = 0
    severe_priority: int = 0
    next_due_at: datetime | None = None

    #: Plans whose reminder has come due but whose window has not opened.
    reminders_pending: int = 0
    total_estimated_hours: float = 0.0
    #: Share of plans driven by measured condition rather than by the calendar.
    condition_based: int = 0


# --- Layer 4: Prescriptive Optimisation ---------------------------------------


class PrescriptiveRead(_AssetStamped):
    """An advisory recommendation. Never a command."""

    computed_at: datetime
    recommended_action: RecommendedAction
    advice: str
    priority: RiskLevel
    energy_saving_kwh: float
    cost_saving: float
    confidence: float

    #: Money alone cannot rank a recommendation; impact blends the saving with
    #: the consequence of doing nothing.
    business_impact: BusinessImpact = BusinessImpact.LOW
    expected_health_gain: float = 0.0
    target_component: str | None = None
    impact_statement: str | None = None


class PrescriptiveSummary(BaseModel):
    """Source of the Cockpit's *today's cost saving* KPI."""

    recommendations: int = 0
    total_energy_saving_kwh: float = 0.0
    total_cost_saving: float = 0.0
    top_action: RecommendedAction | None = None

    critical_impact: int = 0
    high_impact: int = 0
    #: Total health the fleet would recover if every recommendation were acted
    #: on — the upside currently being left on the table.
    total_health_gain: float = 0.0


# --- Layer 5: Asset Performance Management -------------------------------------


class ApmRead(_AssetStamped):
    """Reliability engineering and business value for one asset."""

    computed_at: datetime

    health_index: float
    mtbf_hours: float | None = None
    mttr_hours: float | None = None
    availability: float
    reliability: float
    maintainability: float
    criticality: RiskLevel
    lifecycle_stage: LifecycleStage
    failure_count: int

    cost_exposure: float
    maintenance_cost: float
    maintenance_roi: float
    risk_score: float
    business_value: float
    repair_or_replace: str
    rank: int | None = None


class ApmSummary(BaseModel):
    """Fleet-level APM position."""

    average_health_index: float = 0.0
    average_availability: float = 0.0
    average_reliability: float = 0.0
    total_cost_exposure: float = 0.0
    total_maintenance_cost: float = 0.0
    assets_end_of_life: int = 0
    replace_recommended: int = 0


# --- Layer 6: Overall Equipment Efficiency -------------------------------------


class OeeRead(BaseModel):
    """OEE at one aggregation scope."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope_type: ScopeType
    scope_id: uuid.UUID | None = None
    scope_label: str
    asset_type: AssetType | None = None
    computed_at: datetime

    availability: float
    performance: float
    quality: float
    oee: float
    asset_count: int


class OeeSummary(BaseModel):
    """Enterprise headline plus its breakdowns."""

    enterprise: OeeRead | None = None
    by_building: list[OeeRead] = Field(default_factory=list)
    by_department: list[OeeRead] = Field(default_factory=list)
    by_fleet: list[OeeRead] = Field(default_factory=list)
    by_asset_type: list[OeeRead] = Field(default_factory=list)


# --- Cross-layer --------------------------------------------------------------


class IntelligenceSummary(BaseModel):
    """Every layer's headline verdict, for Cockpit section 4.

    This is the Business Intelligence Layer doing the cross-layer aggregation
    so the Presentation Layer never has to fetch six endpoints and merge them.
    """

    anomaly: AnomalySummary = Field(default_factory=AnomalySummary)
    predictive: PredictiveSummary = Field(default_factory=PredictiveSummary)
    preventive: PreventiveSummary = Field(default_factory=PreventiveSummary)
    prescriptive: PrescriptiveSummary = Field(default_factory=PrescriptiveSummary)
    apm: ApmSummary = Field(default_factory=ApmSummary)
    oee: OeeSummary = Field(default_factory=OeeSummary)

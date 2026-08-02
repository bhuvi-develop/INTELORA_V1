/**
 * Intelligence Layer contracts.
 *
 * Every layer's output carries a confidence figure and a human-readable
 * rationale, which is what lets the interface explain *why* alongside *what*.
 * Layers 3 and 4 have no page of their own — their types are consumed inside
 * the Predictive and APM screens and by the Cockpit's cost-saving KPI.
 */

import type {
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
} from './enums'

/** Asset identity carried by every intelligence result. */
interface AssetStamped {
  id: string
  asset_id: string
  asset_code?: string | null
  asset_name?: string | null
  asset_type?: AssetType | null
}

// --- Layer 1: Anomaly Detection ---------------------------------------------

export interface AnomalyResult extends AssetStamped {
  detected_at: string
  telemetry_time: string
  channel: string
  fault_type: FaultType
  severity: AlertSeverity
  anomaly_score: number
  confidence: number
  observed_value?: number | null
  expected_min?: number | null
  expected_max?: number | null
  deviation_sigma?: number | null
  description: string

  /** Why it happened, and what to do about it. */
  root_cause: RootCause
  recommendation?: string | null

  status: AnomalyStatus
  cleared_at?: string | null
}

export interface AnomalySummary {
  today: number
  critical: number
  warning: number
  information: number
  resolved_today: number
  affected_assets: number
  top_fault_type?: FaultType | null
  average_confidence: number

  /** Still unresolved — a different question from "raised today". */
  open_now: number
  cleared_today: number
  top_root_cause?: RootCause | null
}

export interface FaultBreakdown {
  fault_type: FaultType
  label: string
  count: number
  critical: number
  warning: number
}

export interface RootCauseBreakdown {
  root_cause: RootCause
  label: string
  count: number
  affected_assets: number
}

// --- Layer 2: Predictive Maintenance ----------------------------------------

/** Condition of one replaceable subsystem. */
export interface ComponentHealth {
  key: string
  label: string
  score: number
  weight: number
  basis: string
  degraded: boolean
}

export interface PredictiveResult extends AssetStamped {
  computed_at: string
  failure_probability: number
  remaining_useful_life_hours?: number | null
  predicted_failure_at?: string | null
  confidence: number
  risk_level: RiskLevel
  degradation_rate_per_hour?: number | null
  dominant_fault_type?: FaultType | null
  rationale: string

  /** Where to look, not merely how worried to be. */
  component_health: ComponentHealth[]
  weakest_component?: string | null
  weakest_component_score?: number | null

  maintenance_window_start?: string | null
  maintenance_window_end?: string | null
}

export interface PredictiveSummary {
  assets_at_risk: number
  severe: number
  high: number
  average_failure_probability: number
  shortest_rul_hours?: number | null
  next_predicted_failure_at?: string | null
  average_confidence: number
}

// --- Layer 3: Preventive Maintenance ----------------------------------------

/** One item of work within a maintenance plan. */
export interface MaintenanceTask {
  type: MaintenanceTaskType
  description: string
  estimated_hours: number
  /** Added because a subsystem is degraded, not because the interval elapsed. */
  condition_based: boolean
}

/** A single step a technician ticks off. */
export interface ChecklistItem {
  step: number
  description: string
  complete: boolean
}

export interface PreventiveResult extends AssetStamped {
  computed_at: string
  maintenance_due: boolean
  due_at?: string | null
  window_start?: string | null
  window_end?: string | null
  priority: RiskLevel
  task: string
  interval_hours?: number | null
  hours_since_service?: number | null

  /** The work itself, rather than a one-line summary of it. */
  tasks: MaintenanceTask[]
  checklist: ChecklistItem[]
  estimated_duration_hours?: number | null
  reminder_at?: string | null
  triggered_by_component?: string | null
}

export interface PreventiveSummary {
  due_now: number
  due_this_week: number
  severe_priority: number
  next_due_at?: string | null

  reminders_pending: number
  total_estimated_hours: number
  /** Plans driven by measured condition rather than by the calendar. */
  condition_based: number
}

/** One maintenance activity, planned or performed. */
export interface MaintenanceLog extends AssetStamped {
  task_type: MaintenanceTaskType
  title: string
  description?: string | null
  priority: RiskLevel
  outcome: MaintenanceOutcome

  scheduled_for?: string | null
  window_end?: string | null
  started_at?: string | null
  completed_at?: string | null
  duration_hours?: number | null

  checklist: ChecklistItem[]
  performed_by?: string | null
  notes?: string | null
  cost?: number | null

  health_before?: number | null
  health_after?: number | null
  /** Points recovered — how the value of maintenance becomes measurable. */
  health_gain?: number | null
}

export interface MaintenanceCalendarDay {
  date: string
  total: number
  severe: number
  high: number
  estimated_hours: number
  entries: MaintenanceLog[]
}

export interface MaintenanceCalendar {
  start: string
  end: string
  days: MaintenanceCalendarDay[]
  total_scheduled: number
  total_estimated_hours: number
}

export interface MaintenanceHistorySummary {
  completed: number
  scheduled: number
  in_progress: number
  deferred: number
  total_cost: number
  mean_duration_hours?: number | null
  mean_health_gain?: number | null
}

// --- Layer 4: Prescriptive Optimisation -------------------------------------

export interface PrescriptiveResult extends AssetStamped {
  computed_at: string
  recommended_action: RecommendedAction
  advice: string
  priority: RiskLevel
  energy_saving_kwh: number
  cost_saving: number
  confidence: number

  /** Money alone cannot rank advice; impact weighs the cost of inaction too. */
  business_impact: BusinessImpact
  expected_health_gain: number
  target_component?: string | null
  impact_statement?: string | null
}

export interface PrescriptiveSummary {
  recommendations: number
  total_energy_saving_kwh: number
  total_cost_saving: number
  top_action?: RecommendedAction | null

  critical_impact: number
  high_impact: number
  /** Health the fleet would recover if every recommendation were acted on. */
  total_health_gain: number
}

// --- Layer 5: Asset Performance Management ----------------------------------

export interface ApmResult extends AssetStamped {
  computed_at: string

  /* Reliability engineering. */
  health_index: number
  mtbf_hours?: number | null
  mttr_hours?: number | null
  availability: number
  reliability: number
  maintainability: number
  criticality: RiskLevel
  lifecycle_stage: LifecycleStage
  failure_count: number

  /* Business. */
  cost_exposure: number
  maintenance_cost: number
  maintenance_roi: number
  risk_score: number
  business_value: number
  repair_or_replace: string
  rank?: number | null
}

export interface ApmSummary {
  average_health_index: number
  average_availability: number
  average_reliability: number
  total_cost_exposure: number
  total_maintenance_cost: number
  assets_end_of_life: number
  replace_recommended: number
}

// --- Layer 6: Overall Equipment Efficiency ----------------------------------

export interface OeeResult {
  id: string
  scope_type: ScopeType
  scope_id?: string | null
  scope_label: string
  asset_type?: AssetType | null
  computed_at: string

  availability: number
  performance: number
  quality: number
  oee: number
  asset_count: number
}

export interface OeeSummary {
  enterprise?: OeeResult | null
  by_building: OeeResult[]
  by_department: OeeResult[]
  by_fleet: OeeResult[]
  by_asset_type: OeeResult[]
}

// --- Cross-layer -------------------------------------------------------------

/** Every layer's headline verdict, for the Cockpit intelligence band. */
export interface IntelligenceSummary {
  anomaly: AnomalySummary
  predictive: PredictiveSummary
  preventive: PreventiveSummary
  prescriptive: PrescriptiveSummary
  apm: ApmSummary
  oee: OeeSummary
}

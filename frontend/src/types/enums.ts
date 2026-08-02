/**
 * Platform vocabulary.
 *
 * Mirrors `backend/app/schemas/enums.py` exactly. These are the wire values,
 * so a change on either side must be made on both — they will compile
 * independently and fail at runtime otherwise.
 *
 * The status model is three independent dimensions. Health, operation and
 * connectivity are orthogonal: an asset is always all three at once, and
 * collapsing them would make a legitimate combination such as
 * *running · warning · online* impossible to express.
 */

export const ASSET_TYPES = ['laptop_charger', 'mobile_charger', 'air_conditioner'] as const
export type AssetType = (typeof ASSET_TYPES)[number]

/** Condition dimension, derived from the numeric health score. */
export const HEALTH_STATES = ['healthy', 'warning', 'critical'] as const
export type HealthState = (typeof HEALTH_STATES)[number]

/** What the asset is currently doing. */
export const OPERATIONAL_STATES = ['running', 'idle', 'maintenance'] as const
export type OperationalState = (typeof OPERATIONAL_STATES)[number]

/**
 * Whether the platform is hearing from the asset. `unknown` distinguishes
 * "nothing has arrived yet" from a confirmed `offline`.
 */
export const CONNECTIVITY_STATES = ['online', 'offline', 'unknown'] as const
export type ConnectivityState = (typeof CONNECTIVITY_STATES)[number]

/**
 * Where a reading came from. Displayed for trust and audit; never branched on,
 * because the dashboard must not know or care which source is attached.
 */
export const TELEMETRY_SOURCES = [
  'real_sensor',
  'digital_twin',
  'simulator',
  'rest_api',
  'mqtt',
] as const
export type TelemetrySource = (typeof TELEMETRY_SOURCES)[number]

/** Confidence in an individual reading. Unrelated to the OEE quality factor. */
export const DATA_QUALITIES = ['good', 'uncertain', 'bad'] as const
export type DataQuality = (typeof DATA_QUALITIES)[number]

/** How urgent an alert is. Orthogonal to {@link AlertStatus}. */
export const ALERT_SEVERITIES = ['critical', 'warning', 'information'] as const
export type AlertSeverity = (typeof ALERT_SEVERITIES)[number]

/** Where an alert sits in its lifecycle. Orthogonal to severity. */
export const ALERT_STATUSES = ['active', 'acknowledged', 'resolved'] as const
export type AlertStatus = (typeof ALERT_STATUSES)[number]

/**
 * The single ranking scale shared by predictive risk, APM criticality and
 * maintenance priority, so one colour vocabulary carries across every module.
 */
export const RISK_LEVELS = ['low', 'moderate', 'high', 'severe'] as const
export type RiskLevel = (typeof RISK_LEVELS)[number]

export const LIFECYCLE_STAGES = ['commissioning', 'normal', 'wear', 'end_of_life'] as const
export type LifecycleStage = (typeof LIFECYCLE_STAGES)[number]

export const FAULT_TYPES = [
  'voltage_spike',
  'voltage_drop',
  'over_current',
  'under_current',
  'power_spike',
  'power_loss',
  'over_temperature',
  'frequency_variation',
  'poor_power_factor',
  'abnormal_energy',
  'device_offline',
  'communication_failure',
  'unexpected_behaviour',
  'adapter_failure',
  'cable_failure',
  'compressor_wear',
  'filter_dirty',
  'relay_failure',
] as const
export type FaultType = (typeof FAULT_TYPES)[number]

/**
 * Lifecycle of a detected anomaly.
 *
 * Distinct from alert lifecycle: an anomaly is an observation the platform
 * made and it clears on its own when the condition passes. Most never become
 * alerts.
 */
export const ANOMALY_STATUSES = ['open', 'cleared', 'suppressed'] as const
export type AnomalyStatus = (typeof ANOMALY_STATUSES)[number]

/**
 * Diagnosed origin of an anomaly.
 *
 * The fault type says what was seen; the root cause says why. Two assets can
 * report the same symptom for unrelated reasons, and the remedy follows the
 * cause, not the symptom.
 */
export const ROOT_CAUSES = [
  'supply_instability',
  'thermal_dissipation',
  'airflow_restriction',
  'component_degradation',
  'connection_integrity',
  'load_mismatch',
  'reactive_loading',
  'mechanical_wear',
  'network_path',
  'power_interruption',
  'metering_fault',
  'undetermined',
] as const
export type RootCause = (typeof ROOT_CAUSES)[number]

/** How much a prescriptive recommendation is worth acting on. */
export const BUSINESS_IMPACTS = [
  'critical',
  'high',
  'moderate',
  'low',
  'negligible',
] as const
export type BusinessImpact = (typeof BUSINESS_IMPACTS)[number]

/** Categories of work a maintenance plan can call for. */
export const MAINTENANCE_TASK_TYPES = [
  'inspection',
  'cleaning',
  'calibration',
  'component_replacement',
  'thermal_service',
  'electrical_test',
  'firmware',
] as const
export type MaintenanceTaskType = (typeof MAINTENANCE_TASK_TYPES)[number]

/** How a recorded maintenance activity concluded. */
export const MAINTENANCE_OUTCOMES = [
  'scheduled',
  'in_progress',
  'completed',
  'deferred',
  'cancelled',
] as const
export type MaintenanceOutcome = (typeof MAINTENANCE_OUTCOMES)[number]

/** Behaviours the Digital Twin can drive a device through. Not asset states. */
export const TWIN_SCENARIOS = [
  'healthy',
  'degrading',
  'failure',
  'recovery',
  'maintenance',
  'offline',
] as const
export type TwinScenario = (typeof TWIN_SCENARIOS)[number]

/** Prescriptive outcomes. All advisory — the platform never commands. */
export const RECOMMENDED_ACTIONS = [
  'continue_monitoring',
  'reduce_load',
  'increase_setpoint',
  'schedule_inspection',
  'clean_filter',
  'replace_component',
  'replace_asset',
] as const
export type RecommendedAction = (typeof RECOMMENDED_ACTIONS)[number]

/**
 * Battery charging phase, for categories that charge a battery.
 *
 * Travels with the reading because current and power behave completely
 * differently in each phase — a constant-voltage taper looks identical to a
 * power loss unless you know which one you are seeing.
 */
export const CHARGING_STATES = [
  'idle',
  'charging',
  'topping_off',
  'trickle',
  'complete',
] as const
export type ChargingState = (typeof CHARGING_STATES)[number]

/**
 * Named history windows. The range determines which storage tier answers the
 * query, so these are fixed rather than free-form.
 */
export const TIME_RANGES = [
  'live',
  'last_hour',
  'today',
  'last_7_days',
  'last_30_days',
] as const
export type TimeRange = (typeof TIME_RANGES)[number]

export const SCOPE_TYPES = [
  'enterprise',
  'organization',
  'building',
  'department',
  'fleet',
  'asset',
] as const
export type ScopeType = (typeof SCOPE_TYPES)[number]

/** Semantic colour intent, used by tone-aware components. */
export type Tone = 'primary' | 'healthy' | 'warning' | 'critical' | 'neutral'

/**
 * Domain contracts — assets, telemetry, alerts.
 *
 * Two models live here and the distinction matters more than any other in the
 * codebase:
 *
 * - {@link Asset} and {@link TelemetryReading} describe what a device actually
 *   reports, which differs by category.
 * - {@link AssetBusinessModel} is identical for every category and is what
 *   dashboard surfaces bind to.
 *
 * **Never bind a dashboard surface to telemetry shape.** A new asset category
 * integrates by satisfying the business model; anything reading raw channels
 * would need changing, which is exactly what the architecture forbids.
 */

import type {
  AlertSeverity,
  AlertStatus,
  AssetType,
  ChargingState,
  ConnectivityState,
  DataQuality,
  FaultType,
  HealthState,
  LifecycleStage,
  OperationalState,
  TelemetrySource,
} from './enums'

/**
 * Which telemetry channels a category reports.
 *
 * Components read capabilities instead of branching on `asset_type`, so a new
 * category needs no presentation change. A `false` channel must render as
 * "not reported" — never as zero, which would silently corrupt fleet averages.
 */
export interface AssetCapabilities {
  /* Electrical */
  voltage: boolean
  current: boolean
  power: boolean
  reactive_power: boolean
  apparent_power: boolean
  energy: boolean
  frequency: boolean
  power_factor: boolean
  temperature: boolean

  /* Operating context — reported by every category */
  runtime: boolean
  load: boolean

  /* Asset-specific */
  relay: boolean
  battery: boolean
  charge_cycles: boolean
  fast_charging: boolean
  indoor_temperature: boolean
}

/** Position in the organisation → location → group hierarchy. */
export interface AssetScope {
  organization_id: string
  organization_name?: string | null
  location_id?: string | null
  location_name?: string | null
  building?: string | null
  department?: string | null
  asset_group_id?: string | null
  asset_group_name?: string | null
}

/** Full asset identity and current state. */
export interface Asset {
  id: string
  asset_code: string
  name: string
  asset_type: AssetType
  manufacturer?: string | null
  model?: string | null
  serial_number?: string | null

  rated_power_w: number
  rated_voltage_v: number
  commissioned_at?: string | null

  health_score: number
  health_state: HealthState
  operational_state: OperationalState
  connectivity_state: ConnectivityState
  lifecycle_stage: LifecycleStage

  last_seen_at?: string | null
  operating_hours: number
  lifetime_energy_kwh: number
  relay_operations: number

  scope?: AssetScope | null
  capabilities?: AssetCapabilities | null
}

/**
 * The unified contract every asset exposes, whatever its category.
 *
 * `cost`, `efficiency` and `business_score` are Business Intelligence Layer
 * outputs, not measurements. `cost` is a run-rate per hour, never a total.
 */
export interface AssetBusinessModel {
  asset_id: string
  asset_code: string
  name: string
  asset_type: AssetType

  health_score: number
  health_state: HealthState
  operational_state: OperationalState
  connectivity_state: ConnectivityState

  power_w?: number | null
  temperature_c?: number | null
  energy_kwh?: number | null

  cost: number
  efficiency: number
  business_score: number

  active_alerts: number
  last_seen_at?: string | null
}

/** Fleet roll-up for one category, backing the three premium asset cards. */
export interface AssetTypeSummary {
  asset_type: AssetType
  label: string
  total: number
  healthy: number
  warning: number
  critical: number
  online: number

  average_health: number
  total_power_w?: number | null
  average_temperature_c?: number | null
  total_energy_kwh?: number | null
  efficiency: number
  active_alerts: number

  capabilities: AssetCapabilities
  /** Recent average-health samples, for the card sparkline. */
  trend: number[]
}

/** One reading. Channels absent for the category are `null`. */
export interface TelemetryReading {
  asset_id: string
  time: string

  voltage_v?: number | null
  current_a?: number | null
  power_w?: number | null
  reactive_power_var?: number | null
  apparent_power_va?: number | null
  energy_kwh?: number | null
  frequency_hz?: number | null
  power_factor?: number | null
  temperature_c?: number | null

  /* Operating context, common to every category */
  runtime_hours?: number | null
  load_percent?: number | null

  /* Actuation state — observed, never commanded */
  relay_status?: boolean | null
  relay_operations?: number | null

  /* Asset-specific */
  charging_state?: ChargingState | null
  battery_percent?: number | null
  charge_cycles?: number | null
  fast_charging?: boolean | null
  indoor_temperature_c?: number | null

  /* Derived by the platform's Health Engine, never by the data source. */
  health_score?: number | null
  health_state?: HealthState | null

  operational_state?: OperationalState | null
  connectivity_state?: ConnectivityState | null

  source: TelemetrySource
  quality: DataQuality
}

/** One row of the recent-telemetry table. */
export interface TelemetryRow {
  time: string
  asset_id: string
  asset_code: string
  asset_name: string
  asset_type: AssetType
  voltage_v?: number | null
  current_a?: number | null
  power_w?: number | null
  energy_kwh?: number | null
  temperature_c?: number | null
  frequency_hz?: number | null
  power_factor?: number | null
  health_score?: number | null
  health_state?: HealthState | null
  quality: string
}

export interface SeriesPoint {
  t: string
  v?: number | null
}

/** A named, unit-bearing series ready for charting. */
export interface ChartSeries {
  key: string
  label: string
  /** Travels with the data so axis labels cannot drift from what is plotted. */
  unit: string
  points: SeriesPoint[]
}

/** An operator-facing event raised by the Anomaly Detection layer. */
export interface Alert {
  id: string
  asset_id: string
  asset_code?: string | null
  asset_name?: string | null
  asset_type?: AssetType | null

  severity: AlertSeverity
  status: AlertStatus
  fault_type?: FaultType | null

  title: string
  message: string

  /** Evidence, denormalised so the list can show why it fired. */
  channel?: string | null
  observed_value?: number | null
  expected_min?: number | null
  expected_max?: number | null
  anomaly_result_id?: string | null

  triggered_at: string
  acknowledged_at?: string | null
  resolved_at?: string | null
  assigned_to?: string | null
}

export interface AlertSummary {
  total: number
  active: number
  acknowledged: number
  resolved: number
  critical: number
  warning: number
  information: number
  recent: Alert[]
}

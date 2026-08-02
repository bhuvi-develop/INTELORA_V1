/**
 * Dashboard contracts.
 *
 * Page-shaped rather than resource-shaped: the Cockpit arrives as a small
 * number of aggregate payloads assembled by the Business Intelligence Layer,
 * not as a dozen resource calls merged in the browser.
 */

import type { AlertSummary, AssetTypeSummary, ChartSeries } from './domain'
import type { AssetType, HealthState, Tone } from './enums'
import type { IntelligenceSummary } from './intelligence'

/**
 * One executive KPI.
 *
 * `target` is the route the card navigates to. Every KPI is an entry point,
 * and carrying the destination in the payload keeps that mapping in one place
 * rather than hardcoded across views.
 */
export interface KpiValue {
  key: string
  label: string
  value?: number | null
  unit?: string | null
  precision: number
  delta?: number | null
  delta_label?: string | null
  tone: Tone | string
  target?: string | null
  caption?: string | null
}

/** The single dominant verdict at the top of the Cockpit. */
export interface SystemStatus {
  state: HealthState
  headline: string
  detail: string
  assets_total: number
  assets_online: number
  active_alerts: number
  critical_alerts: number
  /** False when no source is reporting; drives the awaiting-telemetry state. */
  live: boolean
  generated_at: string
}

/** One entry in the Cockpit live feed — an event, not a reading. */
export interface ActivityItem {
  id: string
  kind: string
  severity: string
  title: string
  detail: string
  asset_id?: string | null
  asset_code?: string | null
  occurred_at: string
}

/**
 * Energy and its business translation. `coverage` reports the share of the
 * fleet that actually meters energy, so a total is never mistaken for
 * complete.
 */
export interface EnergySummary {
  today_kwh: number
  today_cost: number
  today_saving: number
  lifetime_kwh: number
  live_power_w: number
  currency: string
  tariff_per_kwh: number
  metered_assets: number
  total_assets: number
  coverage: number
}

/** The complete Mission Control payload. */
export interface CockpitOverview {
  organization: string
  generated_at: string
  system_status: SystemStatus
  kpis: KpiValue[]
  asset_types: AssetTypeSummary[]
  intelligence: IntelligenceSummary
  energy: EnergySummary
  alerts: AlertSummary
  activity: ActivityItem[]
}

/** A labelled proportion, for donut and bar charts. */
export interface DistributionSlice {
  key: string
  label: string
  value: number
  tone: Tone | string
}

/** Every Cockpit chart in one payload, so they resolve as one wave. */
export interface ChartBundle {
  generated_at: string
  window_minutes: number
  energy: ChartSeries
  power: ChartSeries
  voltage: ChartSeries
  current: ChartSeries
  temperature: ChartSeries
  power_factor: ChartSeries
  health: ChartSeries
  health_distribution: DistributionSlice[]
  type_distribution: DistributionSlice[]
}

/**
 * The per-second delta pushed over the WebSocket. Only what changes: identity
 * and static structure arrive once over REST.
 */
export interface LiveTick {
  generated_at: string
  system_status: SystemStatus
  kpis: KpiValue[]
  asset_types: AssetTypeSummary[]
  energy: EnergySummary
  live_power_w: number
  fleet_health: number
  samples_ingested: number
}

/** A report the platform can produce. */
export interface ReportDefinition {
  key: string
  name: string
  description: string
  formats: string[]
  columns: string[]
}

/** Platform preferences, persisted server-side. */
export interface PlatformSettings {
  theme: 'dark' | 'light' | 'system'
  language: string
  organization_name: string
  notifications_enabled: boolean
  notify_on_critical: boolean
  notify_on_warning: boolean
  energy_tariff_per_kwh: number
  currency_code: string
  sidebar_collapsed: boolean
  reduced_motion: boolean
}

/** Digital Twin Engine status, for the Settings diagnostics panel. */
export interface TwinStatus {
  running: boolean
  enabled: boolean
  interval_seconds: number
  devices: number
  device_counts: Record<string, number>
  ticks: number
  samples_emitted: number
  devices_offline: number
  last_tick_at?: string | null
  last_tick_duration_ms: number
  overruns: number
  errors: number
  started_at?: string | null
  telemetry?: { stored: number; rejected: number }
  intelligence?: Record<string, unknown>
  websocket?: Record<string, unknown>
}

/** Per-device twin diagnostics. */
export interface TwinDevice {
  asset_code: string
  asset_type: AssetType
  scenario: string
  health_score: number
  temperature_c: number
  active: boolean
  samples: number
}

/**
 * Typed API surface.
 *
 * One function per endpoint, grouped by domain. Components never call these
 * directly — hooks in `src/hooks` wrap them with React Query so caching,
 * retries and invalidation are declared in one place.
 */

import type {
  Alert,
  AlertSummary,
  Asset,
  AssetBusinessModel,
  AssetType,
  AssetTypeSummary,
  AnomalyResult,
  AnomalySummary,
  ApmResult,
  ApmSummary,
  ChartBundle,
  ChartSeries,
  CockpitOverview,
  HealthCheck,
  HealthState,
  IntelligenceSummary,
  KpiValue,
  OeeResult,
  OeeSummary,
  Page,
  PlatformSettings,
  PredictiveResult,
  PredictiveSummary,
  PrescriptiveResult,
  PreventiveResult,
  PreventiveSummary,
  ReportDefinition,
  RiskLevel,
  ScopeType,
  TelemetryReading,
  TelemetryRow,
  TwinDevice,
  TwinScenario,
  TwinStatus,
} from '@/types'
import { download, http } from './http'

// --- Dashboard ---------------------------------------------------------------

export const dashboardApi = {
  overview: () => http.get<CockpitOverview>('/dashboard/overview'),
  kpis: () => http.get<KpiValue[]>('/dashboard/kpi'),
  charts: () => http.get<ChartBundle>('/dashboard/charts'),
  intelligence: () => http.get<IntelligenceSummary>('/dashboard/intelligence'),
  recent: (limit = 40) =>
    http.get<TelemetryRow[]>('/dashboard/recent', { params: { limit } }),
}

// --- Assets ------------------------------------------------------------------

export interface AssetListParams {
  page?: number
  page_size?: number
  asset_type?: AssetType
  health?: HealthState
  operational?: string
  connectivity?: string
  search?: string
  sort?: 'asset_code' | 'name' | 'health_score' | 'last_seen_at'
  direction?: 'asc' | 'desc'
}

export const assetsApi = {
  list: (params: AssetListParams = {}) =>
    http.get<Page<Asset>>('/assets', { params: params as Record<string, unknown> }),
  business: (assetType?: AssetType, health?: HealthState) =>
    http.get<AssetBusinessModel[]>('/assets/business', {
      params: { asset_type: assetType, health },
    }),
  summary: () => http.get<AssetTypeSummary[]>('/assets/summary'),
  detail: (assetId: string) => http.get<Asset>(`/assets/${assetId}`),
  detailBusiness: (assetId: string) =>
    http.get<AssetBusinessModel>(`/assets/${assetId}/business`),
  /** Latest raw reading, including this category's specific channels. */
  latestTelemetry: (assetId: string) =>
    http.get<TelemetryReading | null>(`/assets/${assetId}/telemetry`),
}

// --- Telemetry ---------------------------------------------------------------

export interface TelemetryHistoryParams {
  asset_id?: string
  asset_type?: AssetType
  channels?: string
  minutes?: number
  points?: number
}

export const telemetryApi = {
  history: (params: TelemetryHistoryParams) =>
    http.get<ChartSeries[]>('/telemetry/history', {
      params: params as Record<string, unknown>,
    }),
  live: (assetType?: AssetType) =>
    http.get<TelemetryReading[]>('/telemetry/live', { params: { asset_type: assetType } }),
  query: (params: Record<string, unknown>) =>
    http.get<Page<TelemetryRow>>('/telemetry', { params }),
}

// --- Alerts ------------------------------------------------------------------

export interface AlertListParams {
  page?: number
  page_size?: number
  severity?: string
  status?: string
  asset_id?: string
  asset_type?: AssetType
  search?: string
}

export const alertsApi = {
  list: (params: AlertListParams = {}) =>
    http.get<Page<Alert>>('/alerts', { params: params as Record<string, unknown> }),
  summary: () => http.get<AlertSummary>('/alerts/summary'),
  detail: (alertId: string) => http.get<Alert>(`/alerts/${alertId}`),
  update: (alertId: string, body: { status?: string; assigned_to?: string }) =>
    http.put<Alert>(`/alerts/${alertId}`, body),
  dismiss: (alertId: string) => http.delete<null>(`/alerts/${alertId}`),
}

// --- Intelligence layers -----------------------------------------------------

export const intelligenceApi = {
  /* Layer 1 */
  anomalies: (assetType?: AssetType, limit = 100) =>
    http.get<AnomalyResult[]>('/anomaly', { params: { asset_type: assetType, limit } }),
  anomalySummary: () => http.get<AnomalySummary>('/anomaly/summary'),
  anomaliesForAsset: (assetId: string, limit = 50) =>
    http.get<AnomalyResult[]>(`/anomaly/${assetId}`, { params: { limit } }),
  runAnomalyAnalysis: () => http.post<Record<string, number>>('/anomaly/analyze'),

  /* Layer 2 */
  predictions: (assetType?: AssetType, risk?: RiskLevel) =>
    http.get<PredictiveResult[]>('/predictive', {
      params: { asset_type: assetType, risk },
    }),
  predictiveSummary: () => http.get<PredictiveSummary>('/predictive/summary'),
  runPredictions: () => http.post<Record<string, number>>('/predictive/run'),

  /* Layer 3 — surfaces inside Predictive and APM */
  maintenance: (dueOnly = false, assetType?: AssetType) =>
    http.get<PreventiveResult[]>('/preventive', {
      params: { due_only: dueOnly, asset_type: assetType },
    }),
  preventiveSummary: () => http.get<PreventiveSummary>('/preventive/summary'),
  generateMaintenance: () => http.post<Record<string, number>>('/preventive/generate'),

  /* Layer 4 — advisory only */
  recommendations: (assetType?: AssetType) =>
    http.get<PrescriptiveResult[]>('/prescriptive', {
      params: { asset_type: assetType, actionable_only: true },
    }),
  recompute: () => http.post<Record<string, number>>('/prescriptive/recommend'),

  /* Layer 5 */
  apm: (assetType?: AssetType) =>
    http.get<ApmResult[]>('/apm', { params: { asset_type: assetType } }),
  apmSummary: () => http.get<ApmSummary>('/apm/summary'),
  apmRanking: (limit = 15) => http.get<ApmResult[]>('/apm/ranking', { params: { limit } }),

  /* Layer 6 */
  oee: () => http.get<OeeSummary>('/oee'),
  oeeHistory: (scope: ScopeType = 'enterprise', limit = 120) =>
    http.get<OeeResult[]>('/oee/history', { params: { scope, limit } }),
}

// --- Platform operations -----------------------------------------------------

export const platformApi = {
  settings: () => http.get<PlatformSettings>('/settings'),
  saveSettings: (body: PlatformSettings) => http.put<PlatformSettings>('/settings', body),

  reports: () => http.get<ReportDefinition[]>('/reports'),
  exportReport: (report: string, format: 'csv' | 'json', minutes = 1440) =>
    download(
      '/reports/export',
      { report, format, minutes },
      `intelora-${report}-${new Date().toISOString().slice(0, 10)}.${format}`,
    ),

  twinStatus: () => http.get<TwinStatus>('/twin/status'),
  twinDevices: (limit = 60) =>
    http.get<TwinDevice[]>('/twin/devices', { params: { limit } }),
  twinStart: () => http.post<TwinStatus>('/twin/start'),
  twinStop: () => http.post<TwinStatus>('/twin/stop'),
  twinReset: () => http.post<TwinStatus>('/twin/reset'),
  twinScenario: (assetId: string, scenario: TwinScenario) =>
    http.post<Record<string, string>>('/twin/scenario', {
      asset_id: assetId,
      scenario,
    }),

  health: () => http.root<HealthCheck>('/health'),
}

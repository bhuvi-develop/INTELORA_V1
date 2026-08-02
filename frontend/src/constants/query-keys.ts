/**
 * React Query key factory.
 *
 * Centralised so that invalidation is precise. Keys are hierarchical: pushing
 * a live tick can refresh `['dashboard']` without disturbing `['alerts']`, and
 * acknowledging an alert invalidates the alert tree without re-fetching the
 * whole Cockpit.
 */

import type { AssetType, HealthState } from '@/types'

export const queryKeys = {
  dashboard: {
    all: ['dashboard'] as const,
    overview: () => [...queryKeys.dashboard.all, 'overview'] as const,
    kpis: () => [...queryKeys.dashboard.all, 'kpi'] as const,
    charts: () => [...queryKeys.dashboard.all, 'charts'] as const,
    intelligence: () => [...queryKeys.dashboard.all, 'intelligence'] as const,
    recent: (limit: number) => [...queryKeys.dashboard.all, 'recent', limit] as const,
  },

  assets: {
    all: ['assets'] as const,
    list: (filters: Record<string, unknown>) =>
      [...queryKeys.assets.all, 'list', filters] as const,
    business: (assetType?: AssetType, health?: HealthState) =>
      [...queryKeys.assets.all, 'business', assetType ?? null, health ?? null] as const,
    summary: () => [...queryKeys.assets.all, 'summary'] as const,
    detail: (assetId: string) => [...queryKeys.assets.all, 'detail', assetId] as const,
  },

  telemetry: {
    all: ['telemetry'] as const,
    history: (params: Record<string, unknown>) =>
      [...queryKeys.telemetry.all, 'history', params] as const,
    live: (assetType?: AssetType) =>
      [...queryKeys.telemetry.all, 'live', assetType ?? null] as const,
    query: (params: Record<string, unknown>) =>
      [...queryKeys.telemetry.all, 'query', params] as const,
  },

  alerts: {
    all: ['alerts'] as const,
    list: (filters: Record<string, unknown>) =>
      [...queryKeys.alerts.all, 'list', filters] as const,
    summary: () => [...queryKeys.alerts.all, 'summary'] as const,
    detail: (alertId: string) => [...queryKeys.alerts.all, 'detail', alertId] as const,
  },

  intelligence: {
    all: ['intelligence'] as const,
    anomalies: (assetType?: AssetType) =>
      [...queryKeys.intelligence.all, 'anomaly', assetType ?? null] as const,
    anomalySummary: () => [...queryKeys.intelligence.all, 'anomaly', 'summary'] as const,
    predictions: (assetType?: AssetType) =>
      [...queryKeys.intelligence.all, 'predictive', assetType ?? null] as const,
    predictiveSummary: () =>
      [...queryKeys.intelligence.all, 'predictive', 'summary'] as const,
    maintenance: (dueOnly: boolean) =>
      [...queryKeys.intelligence.all, 'preventive', dueOnly] as const,
    preventiveSummary: () =>
      [...queryKeys.intelligence.all, 'preventive', 'summary'] as const,
    recommendations: () => [...queryKeys.intelligence.all, 'prescriptive'] as const,
    apm: (assetType?: AssetType) =>
      [...queryKeys.intelligence.all, 'apm', assetType ?? null] as const,
    apmRanking: (limit: number) =>
      [...queryKeys.intelligence.all, 'apm', 'ranking', limit] as const,
    apmSummary: () => [...queryKeys.intelligence.all, 'apm', 'summary'] as const,
    oee: () => [...queryKeys.intelligence.all, 'oee'] as const,
    oeeHistory: (scope: string, limit: number) =>
      [...queryKeys.intelligence.all, 'oee', 'history', scope, limit] as const,
  },

  platform: {
    all: ['platform'] as const,
    settings: () => [...queryKeys.platform.all, 'settings'] as const,
    reports: () => [...queryKeys.platform.all, 'reports'] as const,
    twinStatus: () => [...queryKeys.platform.all, 'twin', 'status'] as const,
    twinDevices: () => [...queryKeys.platform.all, 'twin', 'devices'] as const,
    health: () => [...queryKeys.platform.all, 'health'] as const,
  },
} as const

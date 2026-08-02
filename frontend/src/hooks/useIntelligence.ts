/**
 * Intelligence Layer hooks.
 *
 * The compute triggers all invalidate the whole intelligence tree, not just
 * their own layer. Layers are ordered and dependent — recomputing predictions
 * changes maintenance schedules, which changes recommendations, which changes
 * the Cockpit's cost-saving KPI — so refreshing one in isolation would leave
 * the interface internally inconsistent.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/constants/query-keys'
import { intelligenceApi } from '@/services/api'
import type {
  AnomalyResult,
  AnomalySummary,
  ApmResult,
  ApmSummary,
  AssetType,
  OeeResult,
  OeeSummary,
  PredictiveResult,
  PredictiveSummary,
  PrescriptiveResult,
  PreventiveResult,
  PreventiveSummary,
  RiskLevel,
  ScopeType,
} from '@/types'

// --- Layer 1 -----------------------------------------------------------------

export function useAnomalies(assetType?: AssetType, limit = 100) {
  return useQuery<AnomalyResult[]>({
    queryKey: [...queryKeys.intelligence.anomalies(assetType), limit],
    queryFn: () => intelligenceApi.anomalies(assetType, limit),
    staleTime: 15_000,
  })
}

export function useAnomalySummary() {
  return useQuery<AnomalySummary>({
    queryKey: queryKeys.intelligence.anomalySummary(),
    queryFn: intelligenceApi.anomalySummary,
    staleTime: 20_000,
  })
}

export function useAssetAnomalies(assetId: string | undefined, limit = 40) {
  return useQuery<AnomalyResult[]>({
    queryKey: [...queryKeys.intelligence.all, 'anomaly', 'asset', assetId, limit],
    queryFn: () => intelligenceApi.anomaliesForAsset(assetId as string, limit),
    enabled: Boolean(assetId),
  })
}

// --- Layer 2 -----------------------------------------------------------------

export function usePredictions(assetType?: AssetType, risk?: RiskLevel) {
  return useQuery<PredictiveResult[]>({
    queryKey: [...queryKeys.intelligence.predictions(assetType), risk ?? null],
    queryFn: () => intelligenceApi.predictions(assetType, risk),
    staleTime: 20_000,
  })
}

export function usePredictiveSummary() {
  return useQuery<PredictiveSummary>({
    queryKey: queryKeys.intelligence.predictiveSummary(),
    queryFn: intelligenceApi.predictiveSummary,
    staleTime: 20_000,
  })
}

// --- Layer 3 (surfaces inside Predictive and APM) ----------------------------

export function useMaintenanceSchedule(dueOnly = false, assetType?: AssetType) {
  return useQuery<PreventiveResult[]>({
    queryKey: [...queryKeys.intelligence.maintenance(dueOnly), assetType ?? null],
    queryFn: () => intelligenceApi.maintenance(dueOnly, assetType),
    staleTime: 30_000,
  })
}

export function usePreventiveSummary() {
  return useQuery<PreventiveSummary>({
    queryKey: queryKeys.intelligence.preventiveSummary(),
    queryFn: intelligenceApi.preventiveSummary,
    staleTime: 30_000,
  })
}

// --- Layer 4 (advisory only) --------------------------------------------------

export function useRecommendations(assetType?: AssetType) {
  return useQuery<PrescriptiveResult[]>({
    queryKey: [...queryKeys.intelligence.recommendations(), assetType ?? null],
    queryFn: () => intelligenceApi.recommendations(assetType),
    staleTime: 30_000,
  })
}

// --- Layer 5 -----------------------------------------------------------------

export function useApmResults(assetType?: AssetType) {
  return useQuery<ApmResult[]>({
    queryKey: queryKeys.intelligence.apm(assetType),
    queryFn: () => intelligenceApi.apm(assetType),
    staleTime: 30_000,
  })
}

export function useApmSummary() {
  return useQuery<ApmSummary>({
    queryKey: queryKeys.intelligence.apmSummary(),
    queryFn: intelligenceApi.apmSummary,
    staleTime: 30_000,
  })
}

export function useApmRanking(limit = 15) {
  return useQuery<ApmResult[]>({
    queryKey: queryKeys.intelligence.apmRanking(limit),
    queryFn: () => intelligenceApi.apmRanking(limit),
    staleTime: 30_000,
  })
}

// --- Layer 6 -----------------------------------------------------------------

export function useOee() {
  return useQuery<OeeSummary>({
    queryKey: queryKeys.intelligence.oee(),
    queryFn: intelligenceApi.oee,
    staleTime: 30_000,
  })
}

export function useOeeHistory(scope: ScopeType = 'enterprise', limit = 120) {
  return useQuery<OeeResult[]>({
    queryKey: queryKeys.intelligence.oeeHistory(scope, limit),
    queryFn: () => intelligenceApi.oeeHistory(scope, limit),
    staleTime: 30_000,
  })
}

// --- Compute triggers ---------------------------------------------------------

type Trigger = 'anomaly' | 'predictive' | 'preventive' | 'prescriptive'

const TRIGGERS: Record<Trigger, () => Promise<Record<string, number>>> = {
  anomaly: intelligenceApi.runAnomalyAnalysis,
  predictive: intelligenceApi.runPredictions,
  preventive: intelligenceApi.generateMaintenance,
  prescriptive: intelligenceApi.recompute,
}

/**
 * Run the intelligence pass on demand.
 *
 * Every trigger executes the same ordered pass server-side, because running
 * one layer against stale inputs from the layer above would produce results
 * that contradict each other.
 */
export function useRunIntelligence(trigger: Trigger = 'anomaly') {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: TRIGGERS[trigger],
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.intelligence.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all })
    },
  })
}

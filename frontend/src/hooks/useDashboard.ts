/**
 * Cockpit data hooks.
 *
 * These queries are kept fresh by WebSocket pushes writing into the cache, so
 * their `staleTime` is long and none of them poll. Polling alongside a live
 * stream would double the load to display data the socket has already
 * delivered.
 */

import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/constants/query-keys'
import { dashboardApi } from '@/services/api'
import type {
  ChartBundle,
  CockpitOverview,
  IntelligenceSummary,
  KpiValue,
  TelemetryRow,
} from '@/types'

/** The complete Mission Control payload. Live-patched by the tick handler. */
export function useCockpitOverview() {
  return useQuery<CockpitOverview>({
    queryKey: queryKeys.dashboard.overview(),
    queryFn: dashboardApi.overview,
    staleTime: 60_000,
  })
}

export function useKpis() {
  return useQuery<KpiValue[]>({
    queryKey: queryKeys.dashboard.kpis(),
    queryFn: dashboardApi.kpis,
    staleTime: 60_000,
  })
}

/**
 * All Cockpit charts in one payload.
 *
 * Series are rebuilt server-side from a rolling aggregate, so this refetches
 * on a slow interval rather than arriving over the socket — pushing seven full
 * series every second would be far more traffic than the charts can usefully
 * show.
 */
export function useChartBundle() {
  return useQuery<ChartBundle>({
    queryKey: queryKeys.dashboard.charts(),
    queryFn: dashboardApi.charts,
    staleTime: 10_000,
    refetchInterval: 15_000,
  })
}

export function useIntelligenceSummary() {
  return useQuery<IntelligenceSummary>({
    queryKey: queryKeys.dashboard.intelligence(),
    queryFn: dashboardApi.intelligence,
    staleTime: 30_000,
  })
}

export function useRecentTelemetry(limit = 40) {
  return useQuery<TelemetryRow[]>({
    queryKey: queryKeys.dashboard.recent(limit),
    queryFn: () => dashboardApi.recent(limit),
    staleTime: 5_000,
    refetchInterval: 10_000,
  })
}

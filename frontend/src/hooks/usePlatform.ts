/**
 * Platform operations: settings, reports, Digital Twin control and health.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/constants/query-keys'
import { platformApi, telemetryApi, type TelemetryHistoryParams } from '@/services/api'
import type {
  ChartSeries,
  HealthCheck,
  PlatformSettings,
  ReportDefinition,
  TwinDevice,
  TwinScenario,
  TwinStatus,
} from '@/types'

export function useSettings() {
  return useQuery<PlatformSettings>({
    queryKey: queryKeys.platform.settings(),
    queryFn: platformApi.settings,
    staleTime: 5 * 60_000,
  })
}

export function useSaveSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (settings: PlatformSettings) => platformApi.saveSettings(settings),
    onSuccess: (settings) => {
      queryClient.setQueryData(queryKeys.platform.settings(), settings)
      // The organisation name and tariff both appear on the Cockpit.
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all })
    },
  })
}

export function useReports() {
  return useQuery<ReportDefinition[]>({
    queryKey: queryKeys.platform.reports(),
    queryFn: platformApi.reports,
    staleTime: 10 * 60_000,
  })
}

export function useExportReport() {
  return useMutation({
    mutationFn: ({
      report,
      format,
      minutes,
    }: {
      report: string
      format: 'csv' | 'json'
      minutes?: number
    }) => platformApi.exportReport(report, format, minutes),
  })
}

/**
 * Digital Twin status.
 *
 * Polled rather than pushed: it is diagnostic detail on an engineering panel,
 * not a dashboard surface, and does not warrant space on the live stream.
 */
export function useTwinStatus(enabled = true) {
  return useQuery<TwinStatus>({
    queryKey: queryKeys.platform.twinStatus(),
    queryFn: platformApi.twinStatus,
    refetchInterval: enabled ? 5_000 : false,
    enabled,
  })
}

export function useTwinDevices(enabled = true, limit = 60) {
  return useQuery<TwinDevice[]>({
    queryKey: [...queryKeys.platform.twinDevices(), limit],
    queryFn: () => platformApi.twinDevices(limit),
    refetchInterval: enabled ? 6_000 : false,
    enabled,
  })
}

export function useTwinControl() {
  const queryClient = useQueryClient()

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.platform.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all })
  }

  return {
    start: useMutation({ mutationFn: platformApi.twinStart, onSuccess: invalidate }),
    stop: useMutation({ mutationFn: platformApi.twinStop, onSuccess: invalidate }),
    reset: useMutation({ mutationFn: platformApi.twinReset, onSuccess: invalidate }),
    scenario: useMutation({
      mutationFn: ({ assetId, scenario }: { assetId: string; scenario: TwinScenario }) =>
        platformApi.twinScenario(assetId, scenario),
      onSuccess: invalidate,
    }),
  }
}

export function usePlatformHealth() {
  return useQuery<HealthCheck>({
    queryKey: queryKeys.platform.health(),
    queryFn: platformApi.health,
    refetchInterval: 30_000,
    retry: 1,
  })
}

/** Downsampled telemetry history for detail charts. */
export function useTelemetryHistory(params: TelemetryHistoryParams, enabled = true) {
  return useQuery<ChartSeries[]>({
    queryKey: queryKeys.telemetry.history(params as Record<string, unknown>),
    queryFn: () => telemetryApi.history(params),
    enabled,
    staleTime: 15_000,
    refetchInterval: 20_000,
  })
}

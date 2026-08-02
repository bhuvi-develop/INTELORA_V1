/**
 * Alert hooks.
 *
 * Mutations invalidate the alert tree rather than patching it. An acknowledged
 * alert may legitimately leave the current page — the user could be filtered
 * to active only — and the server, not the client, decides what belongs on a
 * page.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/constants/query-keys'
import { alertsApi, type AlertListParams } from '@/services/api'
import type { Alert, AlertStatus, AlertSummary, Page } from '@/types'

export function useAlertList(params: AlertListParams) {
  return useQuery<Page<Alert>>({
    queryKey: queryKeys.alerts.list(params as Record<string, unknown>),
    queryFn: () => alertsApi.list(params),
    staleTime: 10_000,
    placeholderData: (previous) => previous,
  })
}

export function useAlertSummary() {
  return useQuery<AlertSummary>({
    queryKey: queryKeys.alerts.summary(),
    queryFn: alertsApi.summary,
    staleTime: 30_000,
  })
}

export function useAlert(alertId: string | undefined) {
  return useQuery<Alert>({
    queryKey: queryKeys.alerts.detail(alertId ?? ''),
    queryFn: () => alertsApi.detail(alertId as string),
    enabled: Boolean(alertId),
  })
}

/** Acknowledge, resolve or assign. */
export function useUpdateAlert() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      alertId,
      status,
      assignedTo,
    }: {
      alertId: string
      status?: AlertStatus
      assignedTo?: string
    }) =>
      alertsApi.update(alertId, {
        ...(status ? { status } : {}),
        ...(assignedTo !== undefined ? { assigned_to: assignedTo } : {}),
      }),

    onSuccess: (alert) => {
      queryClient.setQueryData(queryKeys.alerts.detail(alert.id), alert)
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all })
      // The Cockpit alert band and the navbar badge both read from the
      // overview, so it has to refresh alongside the queue.
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all })
    },
  })
}

export function useDismissAlert() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (alertId: string) => alertsApi.dismiss(alertId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all })
    },
  })
}

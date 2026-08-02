/**
 * Live data bridge.
 *
 * Connects the WebSocket to the React Query cache. Incoming messages are
 * written with `setQueryData` rather than held in context state, which is the
 * key decision in this file: only components subscribed to the affected query
 * re-render. Putting a 1 Hz stream into context would re-render every
 * consumer of that context on every tick, whether or not the value they read
 * had changed.
 *
 * The result is that components use ordinary `useQuery` calls and receive live
 * updates for free, with no knowledge that a socket exists — which is exactly
 * the SSOT's requirement that the dashboard never know where data comes from.
 */

import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { LIVE } from '@/constants/config'
import { queryKeys } from '@/constants/query-keys'
import { liveStream, type ConnectionState } from '@/services/live-stream'
import type {
  AlertSummary,
  CockpitOverview,
  IntelligenceSummary,
  LiveTick,
  TelemetryReading,
} from '@/types'

interface LiveContextValue {
  connection: ConnectionState
  /** True when the stream is open and delivering. */
  streaming: boolean
  /** Rolling buffer of the newest raw readings, for the live feed. */
  readings: TelemetryReading[]
  /** Timestamp of the most recent tick. */
  lastTickAt: string | null
}

export const LiveContext = createContext<LiveContextValue | null>(null)

export function LiveProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [connection, setConnection] = useState<ConnectionState>('closed')
  const [readings, setReadings] = useState<TelemetryReading[]>([])
  const [lastTickAt, setLastTickAt] = useState<string | null>(null)

  // Held in a ref so the effect below never re-subscribes on every tick.
  const bufferRef = useRef<TelemetryReading[]>([])

  useEffect(() => {
    const release = liveStream.acquire()
    const unsubscribers: Array<() => void> = []

    unsubscribers.push(liveStream.onStateChange(setConnection))

    /* The tick carries the Cockpit's volatile fields. Merging rather than
       replacing preserves the parts that only the REST payload provides —
       intelligence summaries and the activity feed — so a live update never
       blanks a section the socket does not send. */
    unsubscribers.push(
      liveStream.on<LiveTick>('tick', (tick) => {
        setLastTickAt(tick.generated_at)

        queryClient.setQueryData<CockpitOverview>(
          queryKeys.dashboard.overview(),
          (current) =>
            current
              ? {
                  ...current,
                  generated_at: tick.generated_at,
                  system_status: tick.system_status,
                  kpis: tick.kpis,
                  asset_types: tick.asset_types,
                  energy: { ...current.energy, ...tick.energy },
                }
              : current,
        )

        queryClient.setQueryData(queryKeys.dashboard.kpis(), tick.kpis)
        queryClient.setQueryData(queryKeys.assets.summary(), tick.asset_types)
      }),
    )

    unsubscribers.push(
      liveStream.on<AlertSummary>('alert', (summary) => {
        queryClient.setQueryData(queryKeys.alerts.summary(), summary)
        queryClient.setQueryData<CockpitOverview>(
          queryKeys.dashboard.overview(),
          (current) => (current ? { ...current, alerts: summary } : current),
        )
        // The queue itself is paginated and filtered, so it is invalidated
        // rather than patched — the server decides what belongs on a page.
        void queryClient.invalidateQueries({ queryKey: queryKeys.alerts.all })
      }),
    )

    unsubscribers.push(
      liveStream.on<IntelligenceSummary>('intelligence', (summary) => {
        queryClient.setQueryData(queryKeys.dashboard.intelligence(), summary)
        queryClient.setQueryData<CockpitOverview>(
          queryKeys.dashboard.overview(),
          (current) => (current ? { ...current, intelligence: summary } : current),
        )
        void queryClient.invalidateQueries({ queryKey: queryKeys.intelligence.all })
      }),
    )

    unsubscribers.push(
      liveStream.on<TelemetryReading[]>('telemetry', (batch) => {
        if (!Array.isArray(batch) || batch.length === 0) return
        // Newest first, bounded — an unbounded buffer on a 1 Hz stream is a
        // memory leak with a slow fuse.
        const next = [...batch.slice().reverse(), ...bufferRef.current].slice(
          0,
          LIVE.telemetryBuffer,
        )
        bufferRef.current = next
        setReadings(next)
      }),
    )

    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      release()
    }
  }, [queryClient])

  const value = useMemo<LiveContextValue>(
    () => ({
      connection,
      streaming: connection === 'open',
      readings,
      lastTickAt,
    }),
    [connection, readings, lastTickAt],
  )

  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>
}

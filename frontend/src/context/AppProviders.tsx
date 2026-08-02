/**
 * Provider composition.
 *
 * Order matters and is not arbitrary:
 *
 * 1. `QueryClientProvider` — everything below may read the cache.
 * 2. `ThemeProvider` — chart theming and tokens resolve from it.
 * 3. `SidebarProvider` — shell layout.
 * 4. `LiveProvider` — writes into the query cache, so it must sit inside it.
 * 5. `BootProvider` — outermost of the UI concerns, since the splash overlays
 *    a dashboard that is already mounting behind it.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { BootProvider } from './BootContext'
import { LiveProvider } from './LiveContext'
import { SidebarProvider } from './SidebarContext'
import { ThemeProvider } from './ThemeContext'

/**
 * Cache policy.
 *
 * Two distinct classes of data, per the SSOT's separation of business data
 * from telemetry, so the defaults here are conservative and individual queries
 * tighten them:
 *
 * - Live surfaces are kept fresh by WebSocket pushes, not polling, so their
 *   `staleTime` can be long — refetching would duplicate work the socket has
 *   already done.
 * - Retry is limited, because a dashboard that hangs for thirty seconds
 *   retrying a dead backend is worse than one that shows a clear offline
 *   state immediately.
 */
function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: (failureCount, error) => {
          // A transport failure is worth one retry; a rejected request is not.
          const status = (error as { status?: number } | null)?.status
          if (status && status >= 400 && status < 500) return false
          return failureCount < 2
        },
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
      },
      mutations: {
        retry: 0,
      },
    },
  })
}

export function AppProviders({ children }: { children: ReactNode }) {
  // Created once per application instance rather than at module scope, so hot
  // reloads and tests each get a clean cache.
  const [queryClient] = useState(createQueryClient)

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <SidebarProvider>
          <LiveProvider>
            <BootProvider>{children}</BootProvider>
          </LiveProvider>
        </SidebarProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

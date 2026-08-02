import { AnimatePresence } from 'framer-motion'
import { Suspense, useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { SplashScreen } from '@/components/boot/SplashScreen'
import { ErrorBoundary } from '@/components/common/ErrorState'
import { CommandPalette, Footer, Sidebar, Topbar } from '@/components/layout'
import { Skeleton, TooltipProvider } from '@/components/ui'
import { LAYOUT } from '@/constants/config'
import { useBoot, useSidebar } from '@/hooks/useAppContext'
import { cn } from '@/utils/cn'

/**
 * The application shell.
 *
 * Holds the fixed sidebar and topbar and renders routed content between them.
 *
 * Two details are load-bearing:
 *
 * - **The splash is rendered as a sibling overlay, not a gate.** Routed
 *   content mounts and fetches underneath it, so when the wordmark clears
 *   there is a populated Cockpit behind rather than an empty page starting to
 *   load.
 * - **Interaction is suppressed while booting**, so a click landing during the
 *   animation cannot navigate somewhere the user never saw.
 */

/** Fallback for lazily-loaded routes. Skeletons only — the design system bans spinners. */
function RouteFallback() {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-32 rounded-[20px]" />
        ))}
      </div>
      <Skeleton className="h-72 rounded-[20px]" />
    </div>
  )
}

export function AppShell() {
  const { collapsed, isMobile } = useSidebar()
  const { booting } = useBoot()
  const location = useLocation()
  const [searchOpen, setSearchOpen] = useState(false)

  const openSearch = useCallback(() => setSearchOpen(true), [])

  // ⌘K / Ctrl+K opens global search from anywhere.
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen((current) => !current)
      }
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [])

  // Every navigation returns to the top. Landing mid-page on a fresh module is
  // disorienting, especially with scroll-triggered section reveals.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [location.pathname])

  const contentOffset = isMobile
    ? 0
    : collapsed
      ? LAYOUT.sidebarCollapsedWidth
      : LAYOUT.sidebarWidth

  return (
    <TooltipProvider delayDuration={200}>
      {/* Ambient grid, masked to fade out below the fold. Provides depth
          without competing with the content. */}
      <div
        className="pointer-events-none fixed inset-0 -z-10 grid-backdrop opacity-60"
        aria-hidden
      />

      <div
        className={cn(
          'min-h-dvh',
          // Suppressed rather than unmounted: the tree below must keep
          // fetching and painting while the splash plays.
          booting && 'pointer-events-none',
        )}
        aria-hidden={booting}
      >
        <Sidebar />

        <div
          className="flex min-h-dvh flex-col transition-[padding] duration-300 ease-out"
          style={{ paddingLeft: contentOffset }}
        >
          <Topbar onOpenSearch={openSearch} />

          <main className="flex-1 px-4 pt-8 pb-4 lg:px-8 lg:pt-10">
            <div className="mx-auto w-full max-w-[1600px]">
              <ErrorBoundary>
                <Suspense fallback={<RouteFallback />}>
                  {/* `mode="wait"` lets the outgoing page finish before the
                      next enters, which avoids two pages overlapping mid-fade. */}
                  <AnimatePresence mode="wait" initial={false}>
                    <Outlet key={location.pathname} />
                  </AnimatePresence>
                </Suspense>
              </ErrorBoundary>

              <Footer />
            </div>
          </main>
        </div>
      </div>

      <CommandPalette open={searchOpen} onOpenChange={setSearchOpen} />
      <SplashScreen />
    </TooltipProvider>
  )
}

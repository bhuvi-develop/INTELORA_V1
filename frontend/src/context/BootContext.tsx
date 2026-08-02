/**
 * Boot sequence state.
 *
 * The splash is an overlay, not a route gate. The dashboard mounts and paints
 * *behind* it, which is what makes the hand-off cinematic rather than a load
 * screen giving way to an empty page — by the time the wordmark clears, the
 * Cockpit has already fetched and rendered.
 *
 * Interaction is suppressed until the sequence completes so a stray click
 * during the animation cannot navigate somewhere unintended.
 *
 * The sequence plays on launch and on refresh, and never on in-app navigation:
 * this provider sits above the router and mounts once per page load.
 */

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { BRAND } from '@/constants/config'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

interface BootContextValue {
  /** True while the splash is on screen. */
  booting: boolean
  /** True once the dashboard is interactive. */
  ready: boolean
  /** Allows the sequence to be cut short — used by the development bypass. */
  complete: () => void
}

export const BootContext = createContext<BootContextValue | null>(null)

export function BootProvider({ children }: { children: ReactNode }) {
  const reducedMotion = usePrefersReducedMotion()

  // Reduced motion still shows the brand, briefly and without movement:
  // removing it entirely would strip the identity, which the SSOT forbids.
  const duration = reducedMotion ? 900 : BRAND.splashDurationMs

  const [booting, setBooting] = useState(true)

  const complete = useCallback(() => setBooting(false), [])

  useEffect(() => {
    const timer = window.setTimeout(complete, duration)
    return () => window.clearTimeout(timer)
  }, [complete, duration])

  // Escape ends the sequence. Sitting through five seconds on every hot reload
  // during development is a real cost, and an accessible skip is good practice
  // regardless.
  useEffect(() => {
    if (!booting) return
    const handle = (event: KeyboardEvent) => {
      if (event.key === 'Escape') complete()
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [booting, complete])

  const value = useMemo<BootContextValue>(
    () => ({ booting, ready: !booting, complete }),
    [booting, complete],
  )

  return <BootContext.Provider value={value}>{children}</BootContext.Provider>
}

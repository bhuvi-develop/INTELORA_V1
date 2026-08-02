/**
 * Sidebar state.
 *
 * Kept in its own context rather than a shared "UI" one so that collapsing the
 * sidebar does not re-render the chart tree. At 1 Hz telemetry the cost of a
 * needless full-tree render is real, and context granularity is the cheapest
 * way to avoid it.
 *
 * Desktop collapse and mobile overlay are distinct concepts: on a phone the
 * sidebar is a temporary sheet, on a desktop it is a permanent rail that can
 * shrink to icons.
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
import { useMediaQuery } from '@/hooks/useMediaQuery'

interface SidebarContextValue {
  /** Desktop: rail is reduced to icons. */
  collapsed: boolean
  toggleCollapsed: () => void
  setCollapsed: (value: boolean) => void

  /** Mobile: sidebar is presented as an overlay sheet. */
  mobileOpen: boolean
  setMobileOpen: (value: boolean) => void

  /** True below the desktop breakpoint. */
  isMobile: boolean
}

export const SidebarContext = createContext<SidebarContextValue | null>(null)

function readStoredCollapsed(): boolean {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(BRAND.storageKeys.sidebar) === 'true'
}

export function SidebarProvider({ children }: { children: ReactNode }) {
  const isMobile = useMediaQuery('(max-width: 1023px)')
  const [collapsed, setCollapsedState] = useState<boolean>(readStoredCollapsed)
  const [mobileOpen, setMobileOpen] = useState(false)

  const setCollapsed = useCallback((value: boolean) => {
    setCollapsedState(value)
    window.localStorage.setItem(BRAND.storageKeys.sidebar, String(value))
  }, [])

  const toggleCollapsed = useCallback(() => {
    setCollapsedState((current) => {
      const next = !current
      window.localStorage.setItem(BRAND.storageKeys.sidebar, String(next))
      return next
    })
  }, [])

  // Returning to desktop must not leave a stale overlay mounted underneath.
  useEffect(() => {
    if (!isMobile) setMobileOpen(false)
  }, [isMobile])

  // The overlay covers the page; scrolling the content behind it is disorienting.
  useEffect(() => {
    if (!mobileOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [mobileOpen])

  const value = useMemo<SidebarContextValue>(
    () => ({
      collapsed,
      toggleCollapsed,
      setCollapsed,
      mobileOpen,
      setMobileOpen,
      isMobile,
    }),
    [collapsed, toggleCollapsed, setCollapsed, mobileOpen, isMobile],
  )

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>
}

/**
 * Theme provider.
 *
 * Dark is the default. Persistence is deliberately pluggable: the SSOT places
 * theme on the user profile, but authentication is a later phase, so the
 * preference lives in `localStorage` today behind an interface that a profile
 * write can satisfy later without touching a single consumer.
 *
 * The initial class is applied by an inline script in `index.html` before
 * first paint. This provider takes over from there — if it were responsible
 * for the first application the page would render in the wrong theme for one
 * frame and visibly flash.
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

export type ThemePreference = 'dark' | 'light' | 'system'
export type ResolvedTheme = 'dark' | 'light'

interface ThemeContextValue {
  /** What the user chose, which may be `system`. */
  preference: ThemePreference
  /** What is actually rendered right now. */
  theme: ResolvedTheme
  setPreference: (preference: ThemePreference) => void
  toggle: () => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

const SYSTEM_QUERY = '(prefers-color-scheme: light)'

function readStoredPreference(): ThemePreference {
  if (typeof window === 'undefined') return 'dark'
  const stored = window.localStorage.getItem(BRAND.storageKeys.theme)
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'dark'
}

function resolve(preference: ThemePreference): ResolvedTheme {
  if (preference !== 'system') return preference
  if (typeof window === 'undefined') return 'dark'
  return window.matchMedia(SYSTEM_QUERY).matches ? 'light' : 'dark'
}

function apply(theme: ResolvedTheme): void {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.classList.toggle('light', theme === 'light')
  root.style.colorScheme = theme
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readStoredPreference)
  const [theme, setTheme] = useState<ResolvedTheme>(() => resolve(readStoredPreference()))

  useEffect(() => {
    const resolved = resolve(preference)
    setTheme(resolved)
    apply(resolved)
    window.localStorage.setItem(BRAND.storageKeys.theme, preference)
  }, [preference])

  // Follow the operating system only while the user has asked us to.
  useEffect(() => {
    if (preference !== 'system') return
    const media = window.matchMedia(SYSTEM_QUERY)
    const handle = () => {
      const resolved: ResolvedTheme = media.matches ? 'light' : 'dark'
      setTheme(resolved)
      apply(resolved)
    }
    media.addEventListener('change', handle)
    return () => media.removeEventListener('change', handle)
  }, [preference])

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next)
  }, [])

  const toggle = useCallback(() => {
    setPreferenceState((current) => (resolve(current) === 'dark' ? 'light' : 'dark'))
  }, [])

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, theme, setPreference, toggle }),
    [preference, theme, setPreference, toggle],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

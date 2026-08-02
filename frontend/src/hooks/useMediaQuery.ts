import { useEffect, useState } from 'react'

/**
 * Subscribe to a CSS media query.
 *
 * Uses `useState` with a lazy initialiser rather than defaulting to `false`,
 * so the first render already knows the viewport. Starting wrong and
 * correcting on effect causes a visible layout jump on mobile.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia(query).matches
  })

  useEffect(() => {
    const media = window.matchMedia(query)
    const handle = (event: MediaQueryListEvent) => setMatches(event.matches)

    setMatches(media.matches)
    media.addEventListener('change', handle)
    return () => media.removeEventListener('change', handle)
  }, [query])

  return matches
}

/** Breakpoints, mirroring the Tailwind scale used across the shell. */
export const useIsMobile = () => useMediaQuery('(max-width: 767px)')
export const useIsTablet = () => useMediaQuery('(min-width: 768px) and (max-width: 1023px)')
export const useIsDesktop = () => useMediaQuery('(min-width: 1024px)')

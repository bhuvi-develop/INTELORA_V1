import { useMediaQuery } from './useMediaQuery'

/**
 * Whether the viewer has asked for reduced motion.
 *
 * Consulted by the splash sequence, KPI count-ups, floating cards and chart
 * animation. The design language leans heavily on movement, which makes
 * honouring this a genuine accessibility obligation rather than a formality.
 */
export function usePrefersReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)')
}

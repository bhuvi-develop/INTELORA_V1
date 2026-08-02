import { useEffect, useRef, useState } from 'react'

import { usePrefersReducedMotion } from './usePrefersReducedMotion'

interface CountUpOptions {
  /** Animation length in milliseconds. */
  duration?: number
  /** Decimal places, used to decide when the value has effectively arrived. */
  precision?: number
}

/**
 * Animate a number towards its target.
 *
 * Two behaviours matter for a live dashboard, and both are why this is not a
 * one-line tween:
 *
 * 1. **It animates from the previous value, not from zero.** On a KPI that
 *    updates every second, replaying 0 → 48,213 each tick would be unreadable
 *    and faintly ridiculous. The first appearance rises from zero; every
 *    update after that eases from wherever it was.
 * 2. **It runs on `requestAnimationFrame` and cancels cleanly.** A stale frame
 *    callback writing into an unmounted component is a classic leak in
 *    dashboards that mount and unmount panels as the user navigates.
 *
 * Under reduced motion the target is applied immediately.
 */
export function useCountUp(
  target: number | null | undefined,
  { duration = 900, precision = 0 }: CountUpOptions = {},
): number | null {
  const reducedMotion = usePrefersReducedMotion()
  const [display, setDisplay] = useState<number | null>(target ?? null)

  const fromRef = useRef(0)
  const frameRef = useRef<number | null>(null)
  const startedRef = useRef(false)

  useEffect(() => {
    if (target === null || target === undefined || Number.isNaN(target)) {
      setDisplay(null)
      return
    }

    if (reducedMotion) {
      setDisplay(target)
      fromRef.current = target
      return
    }

    const from = startedRef.current ? fromRef.current : 0
    startedRef.current = true

    const delta = target - from
    const epsilon = 10 ** -precision / 2

    // Already there: skip the frame loop entirely rather than animating a
    // change too small to see.
    if (Math.abs(delta) < epsilon) {
      setDisplay(target)
      fromRef.current = target
      return
    }

    const start = performance.now()

    const step = (now: number) => {
      const elapsed = now - start
      const progress = Math.min(1, elapsed / duration)
      // Cubic ease-out: quick to move, gentle to settle.
      const eased = 1 - (1 - progress) ** 3
      const value = from + delta * eased

      setDisplay(value)

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step)
      } else {
        fromRef.current = target
        frameRef.current = null
      }
    }

    frameRef.current = requestAnimationFrame(step)

    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current)
        frameRef.current = null
        // Record where the animation stopped so the next update continues
        // from there instead of jumping.
        fromRef.current = display ?? from
      }
    }
    // `display` is intentionally excluded: including it would restart the
    // animation on every frame it sets.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, duration, precision, reducedMotion])

  return display
}

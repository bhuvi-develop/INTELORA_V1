import { useEffect, useState } from 'react'

/**
 * A ticking clock for the navbar.
 *
 * Aligns each tick to the wall-clock second rather than setting a 1000 ms
 * interval. An interval drifts, and a drifting clock in an enterprise header
 * eventually skips a second visibly — which looks like a bug in a product
 * whose entire premise is accurate real-time data.
 */
export function useClock(): Date {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    let timer: number

    const schedule = () => {
      const current = new Date()
      setNow(current)
      // Sleep only until the next second boundary.
      timer = window.setTimeout(schedule, 1000 - current.getMilliseconds())
    }

    schedule()
    return () => window.clearTimeout(timer)
  }, [])

  return now
}

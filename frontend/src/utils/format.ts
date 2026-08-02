/**
 * Presentation formatting.
 *
 * One rule governs this module: **a value that was never measured is not
 * zero.** Several asset categories do not report energy, power factor or
 * frequency, so every formatter distinguishes "no reading" from "a reading of
 * nought" and renders the former as an em dash. Collapsing the two would
 * quietly understate every fleet aggregate on the platform.
 */

/** Rendered in place of a value the asset does not report. */
export const NOT_REPORTED = '—'

function isMissing(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined || Number.isNaN(value)
}

/** Format a number with fixed precision and thousands separators. */
export function formatNumber(
  value: number | null | undefined,
  precision = 0,
): string {
  if (isMissing(value)) return NOT_REPORTED
  return value.toLocaleString(undefined, {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  })
}

/**
 * Format a value with its unit, choosing a sensible magnitude.
 *
 * Watts become kilowatts past a thousand, because a Cockpit tile reading
 * "48,213 W" is harder to parse at a glance than "48.2 kW".
 */
export function formatMetric(
  value: number | null | undefined,
  unit: string,
  precision = 1,
): string {
  if (isMissing(value)) return NOT_REPORTED

  if (unit === 'W' && Math.abs(value) >= 1000) {
    return `${formatNumber(value / 1000, 2)} kW`
  }
  if (unit === 'kWh' && Math.abs(value) >= 1000) {
    return `${formatNumber(value / 1000, 2)} MWh`
  }
  if (!unit) return formatNumber(value, precision)

  return `${formatNumber(value, precision)} ${unit}`
}

/** Format a 0–100 score as a percentage. */
export function formatPercent(
  value: number | null | undefined,
  precision = 1,
): string {
  if (isMissing(value)) return NOT_REPORTED
  return `${formatNumber(value, precision)}%`
}

/** Format a 0–1 ratio as a percentage. */
export function formatRatio(
  value: number | null | undefined,
  precision = 1,
): string {
  if (isMissing(value)) return NOT_REPORTED
  return `${formatNumber(value * 100, precision)}%`
}

/** Format a monetary amount in the platform currency. */
export function formatCurrency(
  value: number | null | undefined,
  currency = 'USD',
  precision = 2,
): string {
  if (isMissing(value)) return NOT_REPORTED
  try {
    return value.toLocaleString(undefined, {
      style: 'currency',
      currency,
      minimumFractionDigits: precision,
      maximumFractionDigits: precision,
    })
  } catch {
    // An unrecognised currency code must not break a dashboard tile.
    return `${formatNumber(value, precision)} ${currency}`
  }
}

/** Compact form for dense tiles: 1.2k, 3.4M. */
export function formatCompact(value: number | null | undefined): string {
  if (isMissing(value)) return NOT_REPORTED
  return value.toLocaleString(undefined, { notation: 'compact', maximumFractionDigits: 1 })
}

/** Duration in hours, expressed in the largest sensible unit. */
export function formatHours(value: number | null | undefined): string {
  if (isMissing(value)) return NOT_REPORTED
  if (value < 1) return `${Math.round(value * 60)} min`
  if (value < 48) return `${formatNumber(value, 1)} h`
  if (value < 24 * 60) return `${formatNumber(value / 24, 1)} days`
  return `${formatNumber(value / (24 * 30), 1)} months`
}

const TIME_FORMAT = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const DATE_FORMAT = new Intl.DateTimeFormat(undefined, {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

const DATETIME_FORMAT = new Intl.DateTimeFormat(undefined, {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function formatTime(value: Date | string | null | undefined): string {
  if (!value) return NOT_REPORTED
  const date = typeof value === 'string' ? new Date(value) : value
  return Number.isNaN(date.getTime()) ? NOT_REPORTED : TIME_FORMAT.format(date)
}

export function formatDate(value: Date | string | null | undefined): string {
  if (!value) return NOT_REPORTED
  const date = typeof value === 'string' ? new Date(value) : value
  return Number.isNaN(date.getTime()) ? NOT_REPORTED : DATE_FORMAT.format(date)
}

export function formatDateTime(value: Date | string | null | undefined): string {
  if (!value) return NOT_REPORTED
  const date = typeof value === 'string' ? new Date(value) : value
  return Number.isNaN(date.getTime()) ? NOT_REPORTED : DATETIME_FORMAT.format(date)
}

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

/** "3 minutes ago", "in 2 days". Used for alert and activity timestamps. */
export function formatRelative(value: Date | string | null | undefined): string {
  if (!value) return NOT_REPORTED
  const date = typeof value === 'string' ? new Date(value) : value
  if (Number.isNaN(date.getTime())) return NOT_REPORTED

  const seconds = (date.getTime() - Date.now()) / 1000
  const thresholds: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['second', 60],
    ['minute', 60],
    ['hour', 24],
    ['day', 30],
    ['month', 12],
    ['year', Number.POSITIVE_INFINITY],
  ]

  let remaining = seconds
  for (const [unit, step] of thresholds) {
    if (Math.abs(remaining) < step) {
      return RELATIVE.format(Math.round(remaining), unit)
    }
    remaining /= step
  }
  return RELATIVE.format(Math.round(remaining), 'year')
}

/** Turn a snake_case enum value into readable prose: `filter_dirty` → `Filter Dirty`. */
export function humanise(value: string | null | undefined): string {
  if (!value) return NOT_REPORTED
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/** Two-letter initials for the profile avatar. */
export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
}

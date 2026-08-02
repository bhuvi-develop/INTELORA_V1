import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'

import { useCountUp } from '@/hooks/useCountUp'
import type { Tone } from '@/types'
import { cn } from '@/utils/cn'
import { NOT_REPORTED, formatNumber } from '@/utils/format'
import { toneStyle } from '@/utils/status'

/**
 * Animated numeral.
 *
 * `null` means the asset does not report this value, and it renders as an em
 * dash rather than a zero. That distinction is load-bearing across the whole
 * platform: mobile chargers have no energy meter, and a card showing "0 kWh"
 * would assert a measurement that was never taken.
 */
export function AnimatedNumber({
  value,
  precision = 0,
  unit,
  className,
  unitClassName,
}: {
  value: number | null | undefined
  precision?: number
  unit?: string | null
  className?: string
  unitClassName?: string
}) {
  const animated = useCountUp(value ?? null, { precision })

  if (value === null || value === undefined) {
    return <span className={cn('text-muted', className)}>{NOT_REPORTED}</span>
  }

  return (
    <span className={cn('tabular', className)} data-numeric>
      {formatNumber(animated ?? 0, precision)}
      {unit ? (
        <span className={cn('ml-1 text-[0.55em] font-medium text-subtle', unitClassName)}>
          {unit}
        </span>
      ) : null}
    </span>
  )
}

/**
 * A labelled value in a detail panel.
 *
 * Deliberately terse — these appear a dozen at a time on the APM page, and any
 * decoration would multiply into noise.
 */
export function MetricRow({
  label,
  value,
  hint,
  tone,
  className,
}: {
  label: string
  value: React.ReactNode
  hint?: string
  tone?: Tone
  className?: string
}) {
  return (
    <div className={cn('flex items-baseline justify-between gap-4 py-2', className)}>
      <span className="text-sm text-muted">{label}</span>
      <span className="flex items-baseline gap-2">
        <span
          className={cn(
            'tabular text-sm font-semibold',
            tone ? toneStyle(tone).text : 'text-foreground',
          )}
        >
          {value}
        </span>
        {hint ? <span className="text-xs text-subtle">{hint}</span> : null}
      </span>
    </div>
  )
}

/**
 * A compact metric tile for module summary bands.
 *
 * Secondary effect tier: fades in, lifts subtly, no glow. The full treatment
 * belongs to the Cockpit's KPI row.
 */
export function MetricTile({
  label,
  value,
  unit,
  precision = 0,
  icon: Icon,
  tone = 'primary',
  caption,
  className,
}: {
  label: string
  value: number | null | undefined
  unit?: string
  precision?: number
  icon?: LucideIcon
  tone?: Tone
  caption?: string
  className?: string
}) {
  const styles = toneStyle(tone)

  return (
    <motion.div
      className={cn(
        'glass-panel lift-secondary flex items-start gap-4 p-5',
        className,
      )}
    >
      {Icon ? (
        <span
          className={cn(
            'grid size-10 shrink-0 place-items-center rounded-[12px] border',
            styles.bg,
            styles.border,
            styles.text,
          )}
        >
          <Icon className="size-4.5" />
        </span>
      ) : null}

      <div className="min-w-0 space-y-1">
        <p className="text-xs font-medium tracking-wide text-subtle uppercase">{label}</p>
        <AnimatedNumber
          value={value}
          precision={precision}
          unit={unit}
          className="font-display text-2xl leading-none font-bold text-foreground"
        />
        {caption ? <p className="truncate text-xs text-subtle">{caption}</p> : null}
      </div>
    </motion.div>
  )
}

/**
 * A labelled bar for bounded 0–1 or 0–100 measures.
 *
 * Used for confidence, availability and the OEE factors — anywhere a number
 * alone is less legible than a number with a sense of scale beside it.
 */
export function MeterRow({
  label,
  /** 0–1. */
  ratio,
  tone = 'primary',
  caption,
  className,
}: {
  label: string
  ratio: number
  tone?: Tone
  caption?: string
  className?: string
}) {
  const percent = Math.max(0, Math.min(100, ratio * 100))
  const styles = toneStyle(tone)

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs font-medium text-muted">{label}</span>
        <span className={cn('tabular text-sm font-semibold', styles.text)}>
          {percent.toFixed(1)}%
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken">
        <div
          className={cn('h-full rounded-full transition-[width] duration-700 ease-out', styles.solid)}
          style={{ width: `${percent}%` }}
        />
      </div>
      {caption ? <p className="text-[11px] text-subtle">{caption}</p> : null}
    </div>
  )
}

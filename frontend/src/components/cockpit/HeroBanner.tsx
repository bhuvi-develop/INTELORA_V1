import { motion } from 'framer-motion'
import { AlertOctagon, CheckCircle2, TriangleAlert } from 'lucide-react'

import { riseIn } from '@/animations/variants'
import { LiveDot } from '@/components/common/StatusPill'
import { Skeleton } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { useClock } from '@/hooks/useClock'
import type { SystemStatus } from '@/types'
import { cn } from '@/utils/cn'
import { formatDate, formatTime } from '@/utils/format'
import { HEALTH_TONE, toneStyle } from '@/utils/status'

/**
 * Mission Control banner.
 *
 * This is the five-second answer. Everything below it is progressive detail,
 * so the banner carries a **single dominant verdict** rather than a row of
 * equally-weighted figures — nine peers is a scan, one sentence is an answer.
 *
 * The verdict escalates on the worst condition present, not on an average. An
 * average hides the one asset that is failing, which is precisely the asset
 * the user opened the dashboard to find.
 *
 * This is primary-tier: it gets the full treatment. It is also the only
 * element on the page that does.
 */

const VERDICT_ICON = {
  healthy: CheckCircle2,
  warning: TriangleAlert,
  critical: AlertOctagon,
} as const

export function HeroBanner({
  organization,
  status,
  loading,
}: {
  organization: string
  status?: SystemStatus
  loading?: boolean
}) {
  const now = useClock()

  if (loading || !status) {
    return (
      <div className="glass-panel space-y-4 p-8">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-10 w-96 max-w-full" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
    )
  }

  const tone = HEALTH_TONE[status.state]
  const styles = toneStyle(tone)
  const Icon = VERDICT_ICON[status.state]

  return (
    <motion.section
      variants={riseIn}
      initial="initial"
      animate="animate"
      className="glass-panel lift-primary relative overflow-hidden p-7 lg:p-9"
    >
      {/* A wash in the verdict colour, so the banner's mood is legible from
          across a room before a word is read. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        style={{
          background: `radial-gradient(ellipse 70% 120% at 88% 0%, var(${styles.cssVar}), transparent 60%)`,
        }}
      />

      <div className="relative flex flex-wrap items-start justify-between gap-8">
        <div className="min-w-0 max-w-3xl space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <LiveDot active={status.live} label={status.live ? 'Live' : 'No signal'} />
            <span className="text-xs text-subtle">
              {STRINGS.cockpit.welcome} · {organization}
            </span>
          </div>

          <div className="flex items-start gap-4">
            <span
              className={cn(
                'mt-1 grid size-11 shrink-0 place-items-center rounded-[14px] border',
                styles.bg,
                styles.border,
                styles.text,
              )}
            >
              <Icon className="size-5" />
            </span>

            <div className="min-w-0 space-y-2">
              <h1
                className={cn(
                  'font-display text-2xl leading-tight font-bold tracking-tight lg:text-[2rem]',
                  styles.text,
                )}
              >
                {status.headline}
              </h1>
              <p className="text-sm leading-relaxed text-muted lg:text-base">
                {status.detail}
              </p>
            </div>
          </div>
        </div>

        {/* Time and the counts behind the verdict. Right-aligned so the
            sentence on the left stays the focal point. */}
        <div className="flex shrink-0 flex-col items-start gap-4 sm:items-end">
          <div className="text-left sm:text-right">
            <p className="tabular font-display text-3xl leading-none font-bold text-foreground">
              {formatTime(now)}
            </p>
            <p className="mt-1 text-xs text-subtle">{formatDate(now)}</p>
          </div>

          <div className="flex items-center gap-5">
            <Stat label="Assets" value={`${status.assets_online}/${status.assets_total}`} caption="online" />
            <span className="h-8 w-px bg-border" aria-hidden />
            <Stat
              label="Alerts"
              value={String(status.active_alerts)}
              caption={`${status.critical_alerts} critical`}
              tone={status.critical_alerts > 0 ? 'critical' : undefined}
            />
          </div>
        </div>
      </div>
    </motion.section>
  )
}

function Stat({
  label,
  value,
  caption,
  tone,
}: {
  label: string
  value: string
  caption: string
  tone?: 'critical'
}) {
  return (
    <div className="text-left sm:text-right">
      <p className="text-[10px] font-semibold tracking-[0.14em] text-subtle uppercase">
        {label}
      </p>
      <p
        className={cn(
          'tabular font-display text-lg leading-tight font-bold',
          tone === 'critical' ? 'text-critical' : 'text-foreground',
        )}
      >
        {value}
      </p>
      <p className="text-[11px] text-subtle">{caption}</p>
    </div>
  )
}

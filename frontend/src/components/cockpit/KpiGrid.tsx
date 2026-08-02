import { motion } from 'framer-motion'
import {
  Activity,
  BellRing,
  Boxes,
  CircleCheck,
  CircleDollarSign,
  Gauge,
  OctagonAlert,
  TriangleAlert,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { riseIn, staggerContainer } from '@/animations/variants'
import { AnimatedNumber } from '@/components/common/Metric'
import { KpiSkeleton } from '@/components/ui'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import type { KpiValue, Tone } from '@/types'
import { cn } from '@/utils/cn'
import { toneStyle } from '@/utils/status'

/**
 * Executive KPI grid.
 *
 * Every card is an entry point — the destination arrives in the payload rather
 * than being hardcoded here, so the mapping between a metric and the module
 * that explains it lives in one place on the server.
 *
 * Primary effect tier: lift, glow, count-up. The floating drift the design
 * system asks for is applied at a very low amplitude and staggered per card;
 * nine elements moving in unison would read as instability rather than life,
 * and it is disabled entirely under reduced motion.
 */

const KPI_ICONS: Record<string, LucideIcon> = {
  total_assets: Boxes,
  healthy_assets: CircleCheck,
  warning_assets: TriangleAlert,
  critical_assets: OctagonAlert,
  average_health: Activity,
  average_oee: Gauge,
  today_energy: Zap,
  today_saving: CircleDollarSign,
  active_alerts: BellRing,
}

function KpiCard({ kpi, index }: { kpi: KpiValue; index: number }) {
  const navigate = useNavigate()
  const reducedMotion = usePrefersReducedMotion()

  const tone = (kpi.tone as Tone) ?? 'neutral'
  const styles = toneStyle(tone)
  const Icon = KPI_ICONS[kpi.key] ?? Activity
  const clickable = Boolean(kpi.target)

  return (
    <motion.button
      type="button"
      variants={riseIn}
      // Very low amplitude, long period, staggered start. Present, but never
      // demanding attention.
      animate={
        reducedMotion
          ? undefined
          : {
              y: [0, -3, 0],
              transition: {
                duration: 7 + (index % 4),
                repeat: Infinity,
                ease: 'easeInOut',
                delay: index * 0.35,
              },
            }
      }
      onClick={() => kpi.target && navigate(kpi.target)}
      disabled={!clickable}
      className={cn(
        'glass-panel lift-primary group relative overflow-hidden p-5 text-left',
        clickable ? 'cursor-pointer' : 'cursor-default',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
      )}
      aria-label={kpi.target ? `${kpi.label}. Open related module.` : kpi.label}
    >
      {/* Tone wash in the corner: enough to identify the card's semantics at a
          glance, faint enough not to compete with the number. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.06] transition-opacity duration-300 group-hover:opacity-[0.12]"
        style={{
          background: `radial-gradient(circle at 100% 0%, var(${styles.cssVar}), transparent 62%)`,
        }}
      />

      <div className="relative space-y-3.5">
        <div className="flex items-start justify-between gap-3">
          <span
            className={cn(
              'grid size-9 place-items-center rounded-[10px] border',
              styles.bg,
              styles.border,
              styles.text,
            )}
          >
            <Icon className="size-4" />
          </span>

          {kpi.unit && kpi.unit !== '%' ? (
            <span className="text-[10px] font-semibold tracking-wider text-subtle uppercase">
              {kpi.unit}
            </span>
          ) : null}
        </div>

        <div className="space-y-1">
          <p className="text-xs font-medium text-muted">{kpi.label}</p>
          <AnimatedNumber
            value={kpi.value}
            precision={kpi.precision}
            unit={kpi.unit === '%' ? '%' : null}
            className="font-display text-[1.75rem] leading-none font-bold text-foreground"
          />
        </div>

        {kpi.caption ? (
          <p className="truncate text-[11px] text-subtle">{kpi.caption}</p>
        ) : null}
      </div>
    </motion.button>
  )
}

export function KpiGrid({
  kpis,
  loading,
}: {
  kpis?: KpiValue[]
  loading?: boolean
}) {
  if (loading || !kpis?.length) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 9 }).map((_, index) => (
          <KpiSkeleton key={index} />
        ))}
      </div>
    )
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="initial"
      animate="animate"
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
    >
      {kpis.map((kpi, index) => (
        <KpiCard key={kpi.key} kpi={kpi} index={index} />
      ))}
    </motion.div>
  )
}

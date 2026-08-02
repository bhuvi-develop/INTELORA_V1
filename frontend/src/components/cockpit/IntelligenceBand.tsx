import { motion } from 'framer-motion'
import {
  Activity,
  ArrowUpRight,
  Gauge,
  ShieldAlert,
  TrendingUp,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { fadeUp, staggerContainer } from '@/animations/variants'
import { Skeleton } from '@/components/ui'
import { ROUTES } from '@/constants/navigation'
import type { IntelligenceSummary, Tone } from '@/types'
import { cn } from '@/utils/cn'
import { formatCurrency, formatHours, formatPercent, humanise } from '@/utils/format'
import { toneStyle } from '@/utils/status'

/**
 * Intelligence summary band.
 *
 * This is what turns an overview into Mission Control: each layer contributes
 * one headline verdict on the landing page, and selecting a tile opens the
 * module that explains it.
 *
 * Layers 3 and 4 have no page of their own, so they appear here as verdicts
 * that link to the screens where their output actually lives — maintenance
 * onto Predictive, optimisation onto Reports.
 *
 * Secondary effect tier: fade and subtle lift. The full treatment belongs to
 * the KPI row above.
 */

interface Tile {
  key: string
  layer: number
  label: string
  icon: LucideIcon
  headline: string
  detail: string
  tone: Tone
  to: string
}

function buildTiles(summary: IntelligenceSummary): Tile[] {
  const { anomaly, predictive, preventive, prescriptive, apm, oee } = summary

  return [
    {
      key: 'anomaly',
      layer: 1,
      label: 'Anomaly Detection',
      icon: ShieldAlert,
      headline: `${anomaly.today}`,
      detail: anomaly.today
        ? `${anomaly.critical} critical · ${anomaly.affected_assets} assets affected`
        : 'No anomalies detected today',
      tone: anomaly.critical > 0 ? 'critical' : anomaly.today > 0 ? 'warning' : 'healthy',
      to: ROUTES.anomaly,
    },
    {
      key: 'predictive',
      layer: 2,
      label: 'Predictive Maintenance',
      icon: TrendingUp,
      headline: `${predictive.assets_at_risk}`,
      detail: predictive.shortest_rul_hours
        ? `Soonest failure in ${formatHours(predictive.shortest_rul_hours)}`
        : 'No failures forecast in range',
      tone: predictive.severe > 0 ? 'critical' : predictive.high > 0 ? 'warning' : 'healthy',
      to: ROUTES.predictive,
    },
    {
      key: 'preventive',
      layer: 3,
      label: 'Maintenance Due',
      icon: Wrench,
      headline: `${preventive.due_now}`,
      detail: preventive.due_this_week
        ? `${preventive.due_this_week} scheduled this week`
        : 'Nothing due in the coming week',
      tone: preventive.severe_priority > 0 ? 'critical' : preventive.due_now > 0 ? 'warning' : 'healthy',
      to: ROUTES.predictive,
    },
    {
      key: 'prescriptive',
      layer: 4,
      label: 'Optimisation',
      icon: Activity,
      headline: formatCurrency(prescriptive.total_cost_saving),
      detail: prescriptive.top_action
        ? `${prescriptive.recommendations} actions · top: ${humanise(prescriptive.top_action)}`
        : 'No actions recommended',
      tone: prescriptive.recommendations > 0 ? 'primary' : 'neutral',
      to: ROUTES.reports,
    },
    {
      key: 'apm',
      layer: 5,
      label: 'Asset Performance',
      icon: Activity,
      headline: formatPercent(apm.average_health_index, 0),
      detail: apm.replace_recommended
        ? `${apm.replace_recommended} replacement${apm.replace_recommended === 1 ? '' : 's'} advised · ${formatCurrency(apm.total_cost_exposure)} exposure`
        : `${formatCurrency(apm.total_cost_exposure)} cost exposure`,
      tone: apm.assets_end_of_life > 0 ? 'warning' : 'primary',
      to: ROUTES.apm,
    },
    {
      key: 'oee',
      layer: 6,
      label: 'Equipment Efficiency',
      icon: Gauge,
      headline: oee.enterprise ? formatPercent(oee.enterprise.oee * 100, 1) : '—',
      detail: oee.enterprise
        ? `A ${formatPercent(oee.enterprise.availability * 100, 0)} · P ${formatPercent(oee.enterprise.performance * 100, 0)} · Q ${formatPercent(oee.enterprise.quality * 100, 0)}`
        : 'Awaiting first computation',
      tone:
        oee.enterprise && oee.enterprise.oee < 0.6
          ? 'warning'
          : oee.enterprise
            ? 'healthy'
            : 'neutral',
      to: ROUTES.oee,
    },
  ]
}

export function IntelligenceBand({
  summary,
  loading,
}: {
  summary?: IntelligenceSummary
  loading?: boolean
}) {
  if (loading || !summary) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-32 rounded-[20px]" />
        ))}
      </div>
    )
  }

  const tiles = buildTiles(summary)

  return (
    <motion.div
      variants={staggerContainer}
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
    >
      {tiles.map((tile) => {
        const styles = toneStyle(tile.tone)
        const Icon = tile.icon

        return (
          <motion.div key={tile.key} variants={fadeUp}>
            <Link
              to={tile.to}
              className="glass-panel lift-secondary group flex h-full flex-col gap-4 p-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span
                    className={cn(
                      'grid size-8 place-items-center rounded-[9px] border',
                      styles.bg,
                      styles.border,
                      styles.text,
                    )}
                  >
                    <Icon className="size-4" />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-foreground">{tile.label}</p>
                    <p className="text-[10px] font-semibold tracking-wider text-subtle uppercase">
                      Layer {tile.layer}
                    </p>
                  </div>
                </div>
                <ArrowUpRight className="size-3.5 shrink-0 text-subtle opacity-0 transition-opacity group-hover:opacity-100" />
              </div>

              <div className="mt-auto space-y-1">
                <p
                  className={cn(
                    'tabular font-display text-2xl leading-none font-bold',
                    styles.text,
                  )}
                >
                  {tile.headline}
                </p>
                <p className="text-xs leading-relaxed text-muted">{tile.detail}</p>
              </div>
            </Link>
          </motion.div>
        )
      })}
    </motion.div>
  )
}

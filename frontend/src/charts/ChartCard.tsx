import { motion } from 'framer-motion'
import { TrendingUp, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { fadeUp } from '@/animations/variants'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, ChartSkeleton } from '@/components/ui'
import { cn } from '@/utils/cn'

/**
 * Chart container.
 *
 * Owns the states a chart can be in — loading, empty, populated — so no page
 * has to reimplement them. Charts sit in the secondary effect tier: a subtle
 * lift on hover, never the full glow treatment reserved for KPI cards.
 */

interface ChartCardProps {
  title: string
  description?: string
  icon?: LucideIcon
  /** Rendered top-right: a range selector, legend or action. */
  action?: ReactNode
  loading?: boolean
  /** True when the query succeeded but there is nothing to plot. */
  empty?: boolean
  emptyMessage?: string
  height?: number
  className?: string
  children: ReactNode
}

export function ChartCard({
  title,
  description,
  icon: Icon = TrendingUp,
  action,
  loading = false,
  empty = false,
  emptyMessage = 'No readings in the selected window.',
  height = 260,
  className,
  children,
}: ChartCardProps) {
  if (loading) {
    return <ChartSkeleton height={height} />
  }

  return (
    <motion.div variants={fadeUp} className={cn('h-full', className)}>
      <Card elevation="secondary" className="flex h-full flex-col overflow-hidden">
        <div className="flex items-start justify-between gap-4 p-6 pb-3">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-[10px] border border-border bg-surface-sunken text-primary">
              <Icon className="size-4" />
            </span>
            <div className="min-w-0">
              <h3 className="font-display text-sm leading-tight font-semibold text-foreground">
                {title}
              </h3>
              {description ? (
                <p className="mt-0.5 truncate text-xs text-subtle">{description}</p>
              ) : null}
            </div>
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </div>

        <div className="min-h-0 flex-1 px-3 pb-4">
          {empty ? (
            <div style={{ height }} className="grid place-items-center">
              <EmptyState variant="chart" message={emptyMessage} />
            </div>
          ) : (
            children
          )}
        </div>
      </Card>
    </motion.div>
  )
}

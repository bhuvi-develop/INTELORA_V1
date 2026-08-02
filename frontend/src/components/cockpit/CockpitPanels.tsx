import { motion } from 'framer-motion'
import { Activity, ArrowUpRight, BellRing, Radio } from 'lucide-react'
import { Link } from 'react-router-dom'

import { fadeIn, fadeUp, staggerContainer } from '@/animations/variants'
import { EmptyState } from '@/components/common/EmptyState'
import { Badge, Card, Skeleton } from '@/components/ui'
import { ROUTES } from '@/constants/navigation'
import type { ActivityItem, AlertSummary } from '@/types'
import { cn } from '@/utils/cn'
import { formatRelative } from '@/utils/format'
import { SEVERITY_TONE, toneStyle } from '@/utils/status'

/**
 * The Cockpit's two bottom panels: recent alerts and the activity feed.
 *
 * These are different things and are kept apart deliberately. Alerts are
 * actionable items with a lifecycle; activity is a narrative of what the
 * platform has observed. Merging them would produce a list where half the rows
 * can be acted on and half cannot.
 */

// --- Recent alerts ------------------------------------------------------------

export function AlertsPanel({
  summary,
  loading,
}: {
  summary?: AlertSummary
  loading?: boolean
}) {
  if (loading) {
    return <Skeleton className="h-80 rounded-[20px]" />
  }

  const recent = summary?.recent ?? []

  return (
    <motion.div variants={fadeUp} className="h-full">
      <Card elevation="secondary" className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-4 border-b border-border p-5">
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-[9px] border border-border bg-surface-sunken text-primary">
              <BellRing className="size-4" />
            </span>
            <div>
              <h3 className="font-display text-sm font-semibold text-foreground">
                Recent Alerts
              </h3>
              <p className="text-xs text-subtle">
                {summary?.active ?? 0} active · {summary?.acknowledged ?? 0} acknowledged
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {summary?.critical ? (
              <Badge tone="critical" size="sm">
                {summary.critical}
              </Badge>
            ) : null}
            {summary?.warning ? (
              <Badge tone="warning" size="sm">
                {summary.warning}
              </Badge>
            ) : null}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {recent.length === 0 ? (
            <EmptyState
              variant="default"
              title="No alerts"
              message="Nothing has breached its expected envelope. The fleet is operating cleanly."
            />
          ) : (
            <ul className="divide-y divide-border">
              {recent.slice(0, 6).map((alert) => {
                const tone = SEVERITY_TONE[alert.severity]
                return (
                  <li key={alert.id}>
                    <Link
                      to={`/alerts/${alert.id}`}
                      className="lift-none group flex items-start gap-3 px-5 py-3.5 hover:bg-surface-sunken/60"
                    >
                      <span
                        className={cn(
                          'mt-1.5 size-2 shrink-0 rounded-full',
                          toneStyle(tone).solid,
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-foreground">
                          {alert.title}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-subtle">
                          {alert.asset_code} · {formatRelative(alert.triggered_at)}
                          {alert.status !== 'active' ? ` · ${alert.status}` : ''}
                        </span>
                      </span>
                      <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 text-subtle opacity-0 transition-opacity group-hover:opacity-100" />
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <div className="border-t border-border p-3">
          <Link
            to={ROUTES.alerts}
            className="flex items-center justify-center gap-1.5 rounded-[10px] py-2 text-xs font-medium text-muted transition-colors hover:bg-surface-sunken hover:text-foreground"
          >
            View all alerts
            <ArrowUpRight className="size-3.5" />
          </Link>
        </div>
      </Card>
    </motion.div>
  )
}

// --- Activity feed -------------------------------------------------------------

const ACTIVITY_TONE: Record<string, string> = {
  critical: 'critical',
  warning: 'warning',
  information: 'primary',
}

export function ActivityFeed({
  items,
  loading,
  streaming,
}: {
  items?: ActivityItem[]
  loading?: boolean
  streaming?: boolean
}) {
  if (loading) {
    return <Skeleton className="h-80 rounded-[20px]" />
  }

  const entries = items ?? []

  return (
    <motion.div variants={fadeUp} className="h-full">
      <Card elevation="secondary" className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-4 border-b border-border p-5">
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-[9px] border border-border bg-surface-sunken text-primary">
              <Activity className="size-4" />
            </span>
            <div>
              <h3 className="font-display text-sm font-semibold text-foreground">
                Activity
              </h3>
              <p className="text-xs text-subtle">What the platform has observed</p>
            </div>
          </div>

          {streaming ? (
            <span className="flex items-center gap-1.5 text-[10px] font-semibold tracking-wider text-healthy uppercase">
              <Radio className="size-3 animate-pulse" />
              Streaming
            </span>
          ) : null}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {entries.length === 0 ? (
            <EmptyState
              variant="default"
              title="Nothing to report"
              message="Platform events will appear here as the intelligence layers observe the fleet."
            />
          ) : (
            <motion.ul
              variants={staggerContainer}
              initial="initial"
              animate="animate"
              className="relative px-5 py-4"
            >
              {/* Timeline spine. */}
              <span
                aria-hidden
                className="absolute top-6 bottom-6 left-[27px] w-px bg-border"
              />

              {entries.slice(0, 8).map((item) => {
                const tone = ACTIVITY_TONE[item.severity] ?? 'neutral'
                return (
                  <motion.li
                    key={item.id}
                    variants={fadeIn}
                    className="relative flex gap-4 py-2.5 pl-0"
                  >
                    <span className="relative z-10 mt-1 grid size-4 shrink-0 place-items-center">
                      <span
                        className={cn(
                          'size-2.5 rounded-full ring-4 ring-surface',
                          toneStyle(tone).solid,
                        )}
                      />
                    </span>

                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="truncate text-sm font-medium text-foreground">
                          {item.title}
                        </span>
                        <span className="shrink-0 text-[11px] whitespace-nowrap text-subtle">
                          {formatRelative(item.occurred_at)}
                        </span>
                      </span>
                      <span className="mt-0.5 block text-xs leading-relaxed text-muted">
                        {item.detail}
                      </span>
                      {item.asset_code ? (
                        <span className="mt-1 block font-mono text-[10px] text-subtle">
                          {item.asset_code}
                        </span>
                      ) : null}
                    </span>
                  </motion.li>
                )
              })}
            </motion.ul>
          )}
        </div>
      </Card>
    </motion.div>
  )
}

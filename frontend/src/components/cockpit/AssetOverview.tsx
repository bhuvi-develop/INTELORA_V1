import { motion } from 'framer-motion'
import { AirVent, ArrowUpRight, Laptop, Smartphone, type LucideIcon } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { riseIn, staggerContainer } from '@/animations/variants'
import { EChart } from '@/charts/EChart'
import { sparklineOption } from '@/charts/options'
import { LiveDot } from '@/components/common/StatusPill'
import { Badge, Skeleton } from '@/components/ui'
import type { AssetType, AssetTypeSummary, Tone } from '@/types'
import { cn } from '@/utils/cn'
import { NOT_REPORTED, formatMetric, formatPercent } from '@/utils/format'
import { healthStateFor, HEALTH_TONE, toneStyle } from '@/utils/status'

/**
 * Asset overview — three premium cards.
 *
 * Bound to the **unified business model**, never to telemetry shape. That is
 * what lets one component render all three categories despite their reporting
 * genuinely different channels: a mobile charger has no energy meter, and the
 * card omits the slot rather than showing a zero that would be indistinguishable
 * from a real measurement of nothing.
 *
 * Capabilities travel with each summary, so adding a fourth category requires
 * no change here at all.
 */

const ASSET_ICONS: Record<AssetType, LucideIcon> = {
  laptop_charger: Laptop,
  mobile_charger: Smartphone,
  air_conditioner: AirVent,
}

function MetricSlot({
  label,
  value,
  /** False when the asset category does not report this channel at all. */
  supported = true,
}: {
  label: string
  value: string
  supported?: boolean
}) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-medium tracking-wider text-subtle uppercase">
        {label}
      </p>
      <p
        className={cn(
          'tabular mt-0.5 truncate text-sm font-semibold',
          supported ? 'text-foreground' : 'text-subtle/60',
        )}
        title={supported ? undefined : `${label} is not reported by this asset type`}
      >
        {supported ? value : NOT_REPORTED}
      </p>
    </div>
  )
}

function AssetTypeCard({ summary }: { summary: AssetTypeSummary }) {
  const navigate = useNavigate()
  const Icon = ASSET_ICONS[summary.asset_type]

  const healthState = healthStateFor(summary.average_health)
  const tone: Tone = summary.total === 0 ? 'neutral' : HEALTH_TONE[healthState]
  const styles = toneStyle(tone)

  const live = summary.online > 0

  return (
    <motion.button
      type="button"
      variants={riseIn}
      onClick={() => navigate(`/assets?asset_type=${summary.asset_type}`)}
      className="glass-panel lift-primary group relative overflow-hidden p-6 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      aria-label={`${summary.label}. Open the filtered asset registry.`}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.06] transition-opacity duration-300 group-hover:opacity-[0.11]"
        style={{
          background: `radial-gradient(ellipse 80% 100% at 100% 0%, var(${styles.cssVar}), transparent 62%)`,
        }}
      />

      <div className="relative space-y-5">
        {/* Header: identity, live state, count. */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3.5">
            <span
              className={cn(
                'grid size-12 shrink-0 place-items-center rounded-[14px] border',
                styles.bg,
                styles.border,
                styles.text,
              )}
            >
              <Icon className="size-5.5" />
            </span>
            <div className="min-w-0">
              <h3 className="font-display text-base leading-tight font-semibold text-foreground">
                {summary.label}
              </h3>
              <p className="mt-1 flex items-center gap-2 text-xs text-subtle">
                <span className="tabular">{summary.total} assets</span>
                <span aria-hidden>·</span>
                <LiveDot active={live} />
                <span className="tabular">{summary.online} online</span>
              </p>
            </div>
          </div>

          <ArrowUpRight className="size-4 shrink-0 text-subtle opacity-0 transition-opacity group-hover:opacity-100" />
        </div>

        {/* Health distribution across the three states. */}
        <div className="flex items-center gap-2">
          <div className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-surface-sunken">
            {summary.total > 0 ? (
              <>
                <span
                  className="h-full bg-healthy"
                  style={{ width: `${(summary.healthy / summary.total) * 100}%` }}
                />
                <span
                  className="h-full bg-warning"
                  style={{ width: `${(summary.warning / summary.total) * 100}%` }}
                />
                <span
                  className="h-full bg-critical"
                  style={{ width: `${(summary.critical / summary.total) * 100}%` }}
                />
              </>
            ) : null}
          </div>
          <Badge tone={tone} size="sm" className="shrink-0 tabular">
            {formatPercent(summary.average_health, 0)}
          </Badge>
        </div>

        {/* Business model slots. Rendered from declared capabilities, so an
            unsupported channel is shown as unreported rather than as zero. */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-3.5 sm:grid-cols-4">
          <MetricSlot
            label="Power"
            value={formatMetric(summary.total_power_w, 'W', 1)}
            supported={summary.capabilities.power}
          />
          <MetricSlot
            label="Temp"
            value={formatMetric(summary.average_temperature_c, '°C', 1)}
            supported={summary.capabilities.temperature}
          />
          <MetricSlot
            label="Energy"
            value={formatMetric(summary.total_energy_kwh, 'kWh', 2)}
            supported={summary.capabilities.energy}
          />
          <MetricSlot label="Efficiency" value={formatPercent(summary.efficiency, 0)} />
        </div>

        {/* Trend sparkline over recent fleet health. */}
        <div className="h-10">
          {summary.trend.length > 1 ? (
            <EChart
              height={40}
              deps={[summary.trend.length, summary.trend.at(-1), tone]}
              buildOption={(theme) => sparklineOption(theme, summary.trend, tone)}
              ariaLabel={`${summary.label} health trend`}
            />
          ) : (
            <div className="flex h-full items-center text-[11px] text-subtle">
              Trend building…
            </div>
          )}
        </div>

        {summary.active_alerts > 0 ? (
          <p className="text-xs text-critical">
            {summary.active_alerts} active {summary.active_alerts === 1 ? 'alert' : 'alerts'}
          </p>
        ) : null}
      </div>
    </motion.button>
  )
}

export function AssetOverview({
  summaries,
  loading,
}: {
  summaries?: AssetTypeSummary[]
  loading?: boolean
}) {
  if (loading || !summaries?.length) {
    return (
      <div className="grid gap-6 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-72 rounded-[20px]" />
        ))}
      </div>
    )
  }

  return (
    <motion.div
      variants={staggerContainer}
      className="grid gap-6 lg:grid-cols-3"
    >
      {summaries.map((summary) => (
        <AssetTypeCard key={summary.asset_type} summary={summary} />
      ))}
    </motion.div>
  )
}

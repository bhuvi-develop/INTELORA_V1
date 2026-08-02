import { Activity, Thermometer, Zap } from 'lucide-react'

import { ChartCard } from '@/charts/ChartCard'
import { EChart } from '@/charts/EChart'
import { donutOption, lineOption } from '@/charts/options'
import {
  ActivityFeed,
  AlertsPanel,
  AssetOverview,
  HeroBanner,
  IntelligenceBand,
  KpiGrid,
} from '@/components/cockpit'
import { ErrorState } from '@/components/common/ErrorState'
import { PageSections, Section } from '@/components/common/Section'
import { PageTransition } from '@/components/layout'
import { STRINGS } from '@/constants/strings'
import { useLive } from '@/hooks/useAppContext'
import { useChartBundle, useCockpitOverview } from '@/hooks/useDashboard'
import type { ChartSeries } from '@/types'

/**
 * Enterprise Cockpit — Mission Control.
 *
 * Aggregates every intelligence layer into one executive screen, and carries
 * executive information *only*. Detail lives in the modules each section links
 * to.
 *
 * The layout obeys the instruction that the dashboard must breathe: seven
 * vertical sections separated by large, consistent gaps, at most two charts
 * per row, and no attempt to fit everything above the fold. The user scrolls,
 * and each section reveals as they reach it.
 *
 * Deliberately *not* here: the full electrical trend set. Voltage, current and
 * power factor belong on Energy Analytics and asset detail — putting every
 * chart on the landing page is exactly the crowding the design direction rules
 * out.
 */
export function CockpitPage() {
  const overview = useCockpitOverview()
  const charts = useChartBundle()
  const { streaming } = useLive()

  if (overview.isError) {
    return (
      <PageTransition>
        <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
      </PageTransition>
    )
  }

  const data = overview.data
  const bundle = charts.data

  /**
   * A series with no points means the rolling window has not filled yet, which
   * is a different state from a failed request and gets different copy.
   */
  const hasPoints = (series?: ChartSeries) => Boolean(series?.points.length)

  return (
    <PageTransition>
      <PageSections>
        {/* 1 — The five-second verdict. */}
        <HeroBanner
          organization={data?.organization ?? 'INTELORA'}
          status={data?.system_status}
          loading={overview.isLoading}
        />

        {/* 2 — Executive indicators. Every card is an entry point. */}
        <Section
          title={STRINGS.cockpit.kpiSection}
          description="Select any indicator to open the module that explains it"
        >
          <KpiGrid kpis={data?.kpis} loading={overview.isLoading} />
        </Section>

        {/* 3 — Asset overview, on the unified business model. */}
        <Section
          title={STRINGS.cockpit.assetSection}
          description={STRINGS.cockpit.assetSubtitle}
        >
          <AssetOverview summaries={data?.asset_types} loading={overview.isLoading} />
        </Section>

        {/* 4 — One headline verdict per intelligence layer. */}
        <Section
          title={STRINGS.cockpit.intelligenceSection}
          description={STRINGS.cockpit.intelligenceSubtitle}
        >
          <IntelligenceBand summary={data?.intelligence} loading={overview.isLoading} />
        </Section>

        {/* 5 — Executive trends. Two charts per row, generous spacing. */}
        <Section
          title={STRINGS.cockpit.chartSection}
          description={
            bundle
              ? `Rolling ${bundle.window_minutes}-minute window across the estate`
              : STRINGS.cockpit.chartSubtitle
          }
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Fleet Health"
              description="Average condition index across all monitored assets"
              icon={Activity}
              loading={charts.isLoading}
              empty={!hasPoints(bundle?.health)}
              emptyMessage="Health trend builds as telemetry accumulates."
            >
              {bundle ? (
                <EChart
                  height={260}
                  deps={[bundle.generated_at]}
                  buildOption={(theme) => lineOption(theme, [bundle.health])}
                  ariaLabel="Fleet health trend"
                />
              ) : null}
            </ChartCard>

            <ChartCard
              title="Power Draw"
              description="Total instantaneous demand across the estate"
              icon={Zap}
              loading={charts.isLoading}
              empty={!hasPoints(bundle?.power)}
              emptyMessage="Power trend builds as telemetry accumulates."
            >
              {bundle ? (
                <EChart
                  height={260}
                  deps={[bundle.generated_at]}
                  buildOption={(theme) => lineOption(theme, [bundle.power])}
                  ariaLabel="Total power trend"
                />
              ) : null}
            </ChartCard>

            <ChartCard
              title="Health Distribution"
              description="How the fleet is spread across the three condition states"
              icon={Activity}
              loading={charts.isLoading}
              empty={!bundle?.health_distribution?.length}
            >
              {bundle ? (
                <EChart
                  height={260}
                  deps={[bundle.generated_at]}
                  buildOption={(theme) =>
                    donutOption(theme, bundle.health_distribution, {
                      centerValue: String(
                        bundle.health_distribution.reduce(
                          (sum, slice) => sum + slice.value,
                          0,
                        ),
                      ),
                      centerLabel: 'assets',
                    })
                  }
                  ariaLabel="Asset health distribution"
                />
              ) : null}
            </ChartCard>

            <ChartCard
              title="Thermal Profile"
              description="Average operating temperature across the estate"
              icon={Thermometer}
              loading={charts.isLoading}
              empty={!hasPoints(bundle?.temperature)}
              emptyMessage="Thermal trend builds as telemetry accumulates."
            >
              {bundle ? (
                <EChart
                  height={260}
                  deps={[bundle.generated_at]}
                  buildOption={(theme) => lineOption(theme, [bundle.temperature])}
                  ariaLabel="Average temperature trend"
                />
              ) : null}
            </ChartCard>
          </div>
        </Section>

        {/* 6 and 7 — Alerts and activity, side by side. */}
        <Section title={STRINGS.cockpit.alertSection} stagger={false}>
          <div className="grid gap-6 xl:grid-cols-2">
            <AlertsPanel summary={data?.alerts} loading={overview.isLoading} />
            <ActivityFeed
              items={data?.activity}
              loading={overview.isLoading}
              streaming={streaming}
            />
          </div>
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default CockpitPage

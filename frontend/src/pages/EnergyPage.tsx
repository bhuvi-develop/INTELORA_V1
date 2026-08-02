import { CircleDollarSign, Gauge, Info, Leaf, Zap } from 'lucide-react'
import { useMemo } from 'react'

import { ChartCard } from '@/charts/ChartCard'
import { EChart } from '@/charts/EChart'
import { barOption, lineOption } from '@/charts/options'
import { ErrorState } from '@/components/common/ErrorState'
import { MetricTile } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { PageHeader, PageTransition } from '@/components/layout'
import { Card } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { useAssetSummaries } from '@/hooks/useAssets'
import { useChartBundle, useCockpitOverview } from '@/hooks/useDashboard'
import { useRecommendations } from '@/hooks/useIntelligence'
import { formatCurrency, formatMetric, formatPercent, humanise } from '@/utils/format'

/**
 * Energy Analytics.
 *
 * The destination for the Cockpit's energy KPI. Also the natural home for the
 * detailed electrical trends — voltage, current and power factor — that would
 * crowd the landing page.
 *
 * The metering-coverage caveat is stated prominently rather than tucked into a
 * footnote. Not every asset category has an energy meter, so a fleet total is
 * genuinely partial, and presenting it as complete would be the kind of quiet
 * overstatement that erodes trust in every other figure on the platform.
 */
export function EnergyPage() {
  const overview = useCockpitOverview()
  const charts = useChartBundle()
  const summaries = useAssetSummaries()
  const recommendations = useRecommendations()

  const energy = overview.data?.energy
  const bundle = charts.data

  /** Energy consumption per category, excluding those without a meter. */
  const byCategory = useMemo(() => {
    const metered = (summaries.data ?? []).filter(
      (summary) => summary.capabilities.energy && summary.total_energy_kwh !== null,
    )
    return {
      categories: metered.map((summary) => summary.label),
      values: metered.map((summary) => Number((summary.total_energy_kwh ?? 0).toFixed(3))),
      unmetered: (summaries.data ?? []).filter((summary) => !summary.capabilities.energy),
    }
  }, [summaries.data])

  const savings = useMemo(() => {
    const rows = recommendations.data ?? []
    return {
      total: rows.reduce((sum, row) => sum + row.cost_saving, 0),
      energy: rows.reduce((sum, row) => sum + row.energy_saving_kwh, 0),
      top: rows.slice(0, 5),
    }
  }, [recommendations.data])

  if (overview.isError) {
    return (
      <PageTransition>
        <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.energy.title}
          description={STRINGS.energy.subtitle}
          icon={Zap}
        />

        <Section stagger>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Consumed today"
              value={energy?.today_kwh ?? null}
              unit="kWh"
              precision={2}
              icon={Zap}
              tone="primary"
              caption="Since midnight UTC"
            />
            <MetricTile
              label="Cost today"
              value={energy?.today_cost ?? null}
              precision={2}
              icon={CircleDollarSign}
              tone="warning"
              caption={
                energy
                  ? `At ${formatCurrency(energy.tariff_per_kwh, energy.currency, 3)}/kWh`
                  : undefined
              }
            />
            <MetricTile
              label="Live demand"
              value={energy?.live_power_w ?? null}
              unit="W"
              precision={0}
              icon={Gauge}
              tone="primary"
              caption="Across the whole estate"
            />
            <MetricTile
              label="Avoidable cost"
              value={savings.total}
              precision={2}
              icon={Leaf}
              tone="healthy"
              caption="From prescriptive recommendations"
            />
          </div>
        </Section>

        {/* Coverage caveat. Stated plainly, in place, not buried. */}
        {energy && energy.coverage < 1 ? (
          <Card elevation="flat" className="flex items-start gap-3 p-5">
            <Info className="mt-0.5 size-4 shrink-0 text-primary" />
            <div className="min-w-0 text-sm">
              <p className="font-medium text-foreground">
                Metering covers {formatPercent(energy.coverage * 100, 0)} of the fleet
              </p>
              <p className="mt-1 leading-relaxed text-muted">
                {energy.metered_assets} of {energy.total_assets} assets report an energy
                channel. Figures above are totals across metered assets only.
                {byCategory.unmetered.length > 0
                  ? ` ${byCategory.unmetered.map((s) => s.label).join(' and ')} carry no energy meter.`
                  : ''}
              </p>
            </div>
          </Card>
        ) : null}

        <Section title="Consumption" stagger={false}>
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Energy Trend"
              description="Cumulative consumption across metered assets"
              icon={Zap}
              loading={charts.isLoading}
              empty={!bundle?.energy.points.length}
            >
              {bundle ? (
                <EChart
                  height={280}
                  deps={[bundle.generated_at]}
                  buildOption={(theme) => lineOption(theme, [bundle.energy])}
                  ariaLabel="Energy consumption trend"
                />
              ) : null}
            </ChartCard>

            <ChartCard
              title="Consumption by Category"
              description="Metered categories only"
              icon={Gauge}
              loading={summaries.isLoading}
              empty={byCategory.categories.length === 0}
              emptyMessage="No metered assets are reporting energy yet."
            >
              <EChart
                height={280}
                deps={[byCategory.values.join()]}
                buildOption={(theme) =>
                  barOption(theme, byCategory.categories, byCategory.values, {
                    unit: ' kWh',
                    tone: 'primary',
                  })
                }
                ariaLabel="Energy by asset category"
              />
            </ChartCard>
          </div>
        </Section>

        {/* The detailed electrical set, kept off the Cockpit to protect it. */}
        <Section
          title="Electrical characteristics"
          description="Detailed trends across the estate"
          stagger={false}
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Voltage"
              description="Average supply voltage"
              loading={charts.isLoading}
              empty={!bundle?.voltage.points.length}
            >
              {bundle ? (
                <EChart
                  height={240}
                  deps={[bundle.generated_at]}
                  buildOption={(theme) => lineOption(theme, [bundle.voltage])}
                  ariaLabel="Voltage trend"
                />
              ) : null}
            </ChartCard>

            <ChartCard
              title="Current"
              description="Average current draw"
              loading={charts.isLoading}
              empty={!bundle?.current.points.length}
            >
              {bundle ? (
                <EChart
                  height={240}
                  deps={[bundle.generated_at]}
                  buildOption={(theme) => lineOption(theme, [bundle.current])}
                  ariaLabel="Current trend"
                />
              ) : null}
            </ChartCard>

            <ChartCard
              title="Power Factor"
              description="Apparent power converted into work"
              loading={charts.isLoading}
              empty={!bundle?.power_factor.points.length}
              className="xl:col-span-2"
            >
              {bundle ? (
                <EChart
                  height={240}
                  deps={[bundle.generated_at]}
                  buildOption={(theme) => lineOption(theme, [bundle.power_factor])}
                  ariaLabel="Power factor trend"
                />
              ) : null}
            </ChartCard>
          </div>
        </Section>

        {savings.top.length > 0 ? (
          <Section
            title="Optimisation opportunities"
            description="Layer 4 recommendations, ordered by the value of acting"
            stagger={false}
          >
            <Card elevation="flat" className="divide-y divide-border">
              {savings.top.map((item) => (
                <div key={item.id} className="flex items-start gap-4 p-5">
                  <span className="grid size-9 shrink-0 place-items-center rounded-[10px] border border-healthy/25 bg-healthy-soft text-healthy">
                    <Leaf className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">
                      {humanise(item.recommended_action)} — {item.asset_code}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-muted">{item.advice}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="tabular text-sm font-semibold text-healthy">
                      {formatCurrency(item.cost_saving)}
                    </p>
                    <p className="tabular text-[11px] text-subtle">
                      {formatMetric(item.energy_saving_kwh, 'kWh', 2)}
                    </p>
                  </div>
                </div>
              ))}
            </Card>
          </Section>
        ) : null}
      </PageSections>
    </PageTransition>
  )
}

export default EnergyPage

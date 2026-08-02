import { Building2, Gauge, Layers, Users } from 'lucide-react'
import { useMemo } from 'react'

import { ChartCard } from '@/charts/ChartCard'
import { EChart } from '@/charts/EChart'
import { barOption, gaugeOption, lineOption } from '@/charts/options'
import { ErrorState } from '@/components/common/ErrorState'
import { MeterRow } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { PageHeader, PageTransition } from '@/components/layout'
import { Card } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { useOee, useOeeHistory } from '@/hooks/useIntelligence'
import type { ChartSeries, OeeResult } from '@/types'
import { formatPercent } from '@/utils/format'

/**
 * Layer 6 — Overall Equipment Efficiency.
 *
 * OEE = Availability × Performance × Quality, shown as the headline gauge with
 * its three factors beside it. Showing the factors alongside the product is
 * essential: an OEE of 62% means something entirely different when it comes
 * from poor availability than from poor quality, and the remedies are
 * unrelated.
 *
 * Note that *quality* here is the OEE factor, not the data-quality flag on a
 * telemetry row. The two share a word and nothing else.
 */

function toneForOee(value: number): 'healthy' | 'warning' | 'critical' {
  if (value >= 0.75) return 'healthy'
  if (value >= 0.55) return 'warning'
  return 'critical'
}

function ScopeChart({
  title,
  description,
  icon,
  results,
  loading,
}: {
  title: string
  description: string
  icon: typeof Building2
  results: OeeResult[]
  loading: boolean
}) {
  return (
    <ChartCard
      title={title}
      description={description}
      icon={icon}
      loading={loading}
      empty={results.length === 0}
      emptyMessage="No results at this aggregation scope yet."
    >
      <EChart
        height={Math.max(200, results.length * 42)}
        deps={[results.length, results[0]?.computed_at]}
        buildOption={(theme) =>
          barOption(
            theme,
            results.map((item) => item.scope_label),
            results.map((item) => Number((item.oee * 100).toFixed(1))),
            { unit: '%', tone: 'primary', max: 100 },
          )
        }
        ariaLabel={title}
      />
    </ChartCard>
  )
}

export function OeePage() {
  const oee = useOee()
  const history = useOeeHistory('enterprise', 120)

  const enterprise = oee.data?.enterprise

  /** Enterprise OEE over time, assembled into the standard series shape. */
  const trend = useMemo<ChartSeries[]>(() => {
    const rows = history.data ?? []
    if (rows.length === 0) return []

    const build = (
      key: string,
      label: string,
      pick: (row: OeeResult) => number,
    ): ChartSeries => ({
      key,
      label,
      unit: '%',
      points: rows.map((row) => ({
        t: row.computed_at,
        v: Number((pick(row) * 100).toFixed(2)),
      })),
    })

    return [
      build('oee', 'OEE', (row) => row.oee),
      build('availability', 'Availability', (row) => row.availability),
      build('performance', 'Performance', (row) => row.performance),
      build('quality', 'Quality', (row) => row.quality),
    ]
  }, [history.data])

  if (oee.isError) {
    return (
      <PageTransition>
        <ErrorState error={oee.error} onRetry={() => void oee.refetch()} />
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.oee.title}
          description={STRINGS.oee.subtitle}
          icon={Gauge}
          layer={6}
        />

        {/* Headline gauge and its three factors. */}
        <Section stagger={false}>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
            <Card elevation="primary" className="flex flex-col items-center p-6">
              <p className="text-xs font-semibold tracking-wider text-subtle uppercase">
                Enterprise OEE
              </p>
              <EChart
                height={280}
                className="w-full"
                deps={[enterprise?.oee, enterprise?.computed_at]}
                buildOption={(theme) =>
                  gaugeOption(theme, enterprise ? enterprise.oee * 100 : null, {
                    label: 'Overall',
                    tone: enterprise ? toneForOee(enterprise.oee) : 'neutral',
                  })
                }
                ariaLabel="Enterprise overall equipment efficiency"
              />
              <p className="tabular text-center text-xs text-subtle">
                {enterprise
                  ? `Across ${enterprise.asset_count} assets`
                  : 'Awaiting first computation'}
              </p>
            </Card>

            <Card elevation="secondary" className="flex flex-col justify-center gap-6 p-7">
              <div>
                <h2 className="font-display text-base font-semibold text-foreground">
                  Factor breakdown
                </h2>
                <p className="mt-1 text-sm text-muted">
                  OEE is the product of these three. The lowest one is where the
                  opportunity is.
                </p>
              </div>

              <div className="space-y-5">
                <MeterRow
                  label="Availability"
                  ratio={enterprise?.availability ?? 0}
                  tone={enterprise ? toneForOee(enterprise.availability) : 'neutral'}
                  caption="Share of the window the fleet was reachable and usable"
                />
                <MeterRow
                  label="Performance"
                  ratio={enterprise?.performance ?? 0}
                  tone={enterprise ? toneForOee(enterprise.performance) : 'neutral'}
                  caption="Output delivered against nameplate expectation while running"
                />
                <MeterRow
                  label="Quality"
                  ratio={enterprise?.quality ?? 0}
                  tone={enterprise ? toneForOee(enterprise.quality) : 'neutral'}
                  caption="Trustworthy output, blending data confidence with asset condition"
                />
              </div>

              {enterprise ? (
                <p className="border-t border-border pt-4 text-xs text-subtle">
                  {formatPercent(enterprise.availability * 100, 1)} ×{' '}
                  {formatPercent(enterprise.performance * 100, 1)} ×{' '}
                  {formatPercent(enterprise.quality * 100, 1)} ={' '}
                  <span className="font-semibold text-foreground">
                    {formatPercent(enterprise.oee * 100, 1)}
                  </span>
                </p>
              ) : null}
            </Card>
          </div>
        </Section>

        <Section
          title="Efficiency over time"
          description="Enterprise OEE and its factors across recent computations"
          stagger={false}
        >
          <ChartCard
            title="OEE Trend"
            description="Each line is a factor; OEE is their product"
            icon={Gauge}
            loading={history.isLoading}
            empty={trend.length === 0}
            emptyMessage="The trend builds as the intelligence layers run."
          >
            <EChart
              height={300}
              deps={[history.data?.length, history.data?.at(-1)?.computed_at]}
              buildOption={(theme) =>
                lineOption(theme, trend, { area: false, showLegend: true })
              }
              ariaLabel="OEE trend over time"
            />
          </ChartCard>
        </Section>

        {/* Aggregation scopes. Department is derived from the location, which
            is where that attribute lives in the schema. */}
        <Section
          title="Comparison by scope"
          description="The same measure rolled up across the organisation hierarchy"
          stagger={false}
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <ScopeChart
              title="By Building"
              description="Efficiency per physical site"
              icon={Building2}
              results={oee.data?.by_building ?? []}
              loading={oee.isLoading}
            />
            <ScopeChart
              title="By Department"
              description="Efficiency per operating department"
              icon={Users}
              results={oee.data?.by_department ?? []}
              loading={oee.isLoading}
            />
            <ScopeChart
              title="By Fleet"
              description="Efficiency per asset group"
              icon={Layers}
              results={oee.data?.by_fleet ?? []}
              loading={oee.isLoading}
            />
            <ScopeChart
              title="By Asset Category"
              description="Efficiency per device type"
              icon={Gauge}
              results={oee.data?.by_asset_type ?? []}
              loading={oee.isLoading}
            />
          </div>
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default OeePage

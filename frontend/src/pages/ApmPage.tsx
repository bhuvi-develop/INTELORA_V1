import { Activity, CircleDollarSign, Clock, ShieldCheck, TrendingDown } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

import { ChartCard } from '@/charts/ChartCard'
import { EChart } from '@/charts/EChart'
import { radarOption, riskMatrixOption, treemapOption } from '@/charts/options'
import { ErrorState } from '@/components/common/ErrorState'
import { MetricTile } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { DataTable, type Column } from '@/components/data'
import { PageHeader, PageTransition } from '@/components/layout'
import { Badge } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { useApmRanking, useApmResults, useApmSummary } from '@/hooks/useIntelligence'
import type { ApmResult } from '@/types'
import { formatCurrency, formatPercent } from '@/utils/format'
import { LIFECYCLE_LABEL, LIFECYCLE_TONE, RISK_LABEL, RISK_TONE } from '@/utils/status'

/**
 * Layer 5 — Asset Performance Management.
 *
 * The richest module, and the one where product principle 4 becomes concrete:
 * reliability engineering and business intelligence are the same data viewed
 * by two different audiences, so the page separates them into two visually
 * distinct bands rather than interleaving MTBF with cost exposure.
 */
export function ApmPage() {
  const navigate = useNavigate()
  const results = useApmResults()
  const summary = useApmSummary()
  const ranking = useApmRanking(12)

  const columns = useMemo<Column<ApmResult>[]>(
    () => [
      {
        key: 'rank',
        header: '#',
        accessor: (row) => row.rank ?? 9999,
        width: '56px',
        render: (row) => (
          <span className="tabular text-xs font-semibold text-subtle">{row.rank ?? '—'}</span>
        ),
      },
      {
        key: 'asset',
        header: 'Asset',
        accessor: (row) => row.asset_code ?? '',
        render: (row) => (
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">
              {row.asset_name ?? 'Unknown'}
            </p>
            <p className="font-mono text-[11px] text-subtle">{row.asset_code}</p>
          </div>
        ),
      },
      {
        key: 'health_index',
        header: 'Health',
        accessor: (row) => row.health_index,
        align: 'right',
        render: (row) => (
          <span className="tabular text-sm font-semibold text-foreground">
            {row.health_index.toFixed(0)}
          </span>
        ),
      },
      {
        key: 'criticality',
        header: 'Criticality',
        accessor: (row) => row.criticality,
        render: (row) => (
          <Badge tone={RISK_TONE[row.criticality]} size="sm">
            {RISK_LABEL[row.criticality]}
          </Badge>
        ),
        hideBelow: 'sm',
      },
      {
        key: 'lifecycle_stage',
        header: 'Lifecycle',
        accessor: (row) => row.lifecycle_stage,
        render: (row) => (
          <Badge tone={LIFECYCLE_TONE[row.lifecycle_stage]} size="sm">
            {LIFECYCLE_LABEL[row.lifecycle_stage]}
          </Badge>
        ),
        hideBelow: 'md',
      },
      {
        key: 'availability',
        header: 'Availability',
        accessor: (row) => row.availability,
        align: 'right',
        render: (row) => (
          <span className="tabular text-sm text-muted">
            {formatPercent(row.availability * 100, 1)}
          </span>
        ),
        hideBelow: 'lg',
      },
      {
        key: 'cost_exposure',
        header: 'Cost exposure',
        accessor: (row) => row.cost_exposure,
        align: 'right',
        render: (row) => (
          <span className="tabular text-sm font-semibold text-foreground">
            {formatCurrency(row.cost_exposure)}
          </span>
        ),
      },
      {
        key: 'repair_or_replace',
        header: 'Advice',
        accessor: (row) => row.repair_or_replace,
        render: (row) => (
          <Badge tone={row.repair_or_replace === 'replace' ? 'critical' : 'healthy'} size="sm">
            {row.repair_or_replace === 'replace' ? 'Replace' : 'Repair'}
          </Badge>
        ),
        hideBelow: 'md',
      },
    ],
    [],
  )

  /** Likelihood against consequence. Top-right is where attention belongs. */
  const matrix = useMemo(
    () =>
      (results.data ?? []).map((row) => ({
        x: Math.min(1, row.risk_score),
        y: row.cost_exposure,
        label: row.asset_code ?? 'Unknown',
        tone: RISK_TONE[row.criticality],
        size: 10 + row.business_value / 220,
      })),
    [results.data],
  )

  /** Business value by asset — where the fleet's worth is concentrated. */
  const treemap = useMemo(
    () =>
      (results.data ?? [])
        .filter((row) => row.business_value > 0)
        .slice(0, 24)
        .map((row) => ({
          name: row.asset_code ?? 'Unknown',
          value: Math.round(row.business_value),
          tone: LIFECYCLE_TONE[row.lifecycle_stage],
        })),
    [results.data],
  )

  /** Fleet reliability profile, averaged across the five bounded measures. */
  const radar = useMemo(() => {
    const rows = results.data ?? []
    if (rows.length === 0) return null

    const mean = (pick: (row: ApmResult) => number) =>
      Number(((rows.reduce((sum, row) => sum + pick(row), 0) / rows.length) * 100).toFixed(1))

    return {
      indicators: [
        { name: 'Availability', max: 100 },
        { name: 'Reliability', max: 100 },
        { name: 'Maintainability', max: 100 },
        { name: 'Health', max: 100 },
        { name: 'Low risk', max: 100 },
      ],
      values: [
        mean((row) => row.availability),
        mean((row) => row.reliability),
        mean((row) => row.maintainability),
        mean((row) => row.health_index / 100),
        mean((row) => 1 - Math.min(1, row.risk_score)),
      ],
    }
  }, [results.data])

  if (results.isError) {
    return (
      <PageTransition>
        <ErrorState error={results.error} onRetry={() => void results.refetch()} />
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.apm.title}
          description={STRINGS.apm.subtitle}
          icon={Activity}
          layer={5}
        />

        {/* Band 1 — reliability engineering. */}
        <Section
          title={STRINGS.apm.reliabilityBand}
          description="How the fleet behaves as equipment"
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Health index"
              value={summary.data?.average_health_index ?? null}
              precision={1}
              icon={Activity}
              tone="primary"
              caption="Fleet average condition"
            />
            <MetricTile
              label="Availability"
              value={
                summary.data ? Number((summary.data.average_availability * 100).toFixed(1)) : null
              }
              unit="%"
              precision={1}
              icon={Clock}
              tone="healthy"
              caption="Reachable and usable"
            />
            <MetricTile
              label="Reliability"
              value={
                summary.data ? Number((summary.data.average_reliability * 100).toFixed(1)) : null
              }
              unit="%"
              precision={1}
              icon={ShieldCheck}
              tone="healthy"
              caption="24-hour survival probability"
            />
            <MetricTile
              label="End of life"
              value={summary.data?.assets_end_of_life ?? null}
              icon={TrendingDown}
              tone={summary.data?.assets_end_of_life ? 'warning' : 'neutral'}
              caption="Assets past service life"
            />
          </div>
        </Section>

        <Section stagger={false}>
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Fleet Reliability Profile"
              description="Five bounded measures, averaged across the estate"
              icon={ShieldCheck}
              loading={results.isLoading}
              empty={!radar}
            >
              {radar ? (
                <EChart
                  height={320}
                  deps={[radar.values.join()]}
                  buildOption={(theme) =>
                    radarOption(theme, radar.indicators, [
                      { name: 'Fleet average', values: radar.values, tone: 'primary' },
                    ])
                  }
                  ariaLabel="Fleet reliability radar"
                />
              ) : null}
            </ChartCard>

            <ChartCard
              title="Risk Matrix"
              description="Failure likelihood against cost consequence — attention belongs top-right"
              icon={TrendingDown}
              loading={results.isLoading}
              empty={matrix.length === 0}
            >
              <EChart
                height={320}
                deps={[matrix.length]}
                buildOption={(theme) => riskMatrixOption(theme, matrix)}
                ariaLabel="Asset risk matrix"
              />
            </ChartCard>
          </div>
        </Section>

        {/* Band 2 — business intelligence. */}
        <Section
          title={STRINGS.apm.businessBand}
          description="What the fleet means financially"
        >
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Cost exposure"
              value={summary.data?.total_cost_exposure ?? null}
              precision={0}
              icon={CircleDollarSign}
              tone={summary.data && summary.data.total_cost_exposure > 0 ? 'warning' : 'neutral'}
              caption="Expected loss if nothing is done"
            />
            <MetricTile
              label="Maintenance cost"
              value={summary.data?.total_maintenance_cost ?? null}
              precision={0}
              tone="primary"
              caption="Cost of acting"
            />
            <MetricTile
              label="Replacement advised"
              value={summary.data?.replace_recommended ?? null}
              tone={summary.data?.replace_recommended ? 'critical' : 'healthy'}
              caption="Where repair no longer pays"
            />
            <MetricTile
              label="Assets ranked"
              value={results.data?.length ?? null}
              tone="neutral"
              caption="Ordered by exposure"
            />
          </div>
        </Section>

        <Section stagger={false}>
          <ChartCard
            title="Business Value Concentration"
            description="Where the fleet's remaining worth sits, coloured by lifecycle stage"
            icon={CircleDollarSign}
            loading={results.isLoading}
            empty={treemap.length === 0}
          >
            <EChart
              height={340}
              deps={[treemap.length]}
              buildOption={(theme) => treemapOption(theme, treemap)}
              ariaLabel="Business value by asset"
            />
          </ChartCard>
        </Section>

        <Section
          title="Asset ranking"
          description="Ordered by cost exposure — the assets most likely to cost money if left alone"
          stagger={false}
        >
          <DataTable
            rows={ranking.data ?? results.data ?? []}
            columns={columns}
            rowKey={(row) => row.id}
            loading={ranking.isLoading}
            pageSize={12}
            searchPlaceholder="Search by asset, criticality or lifecycle…"
            onRowClick={(row) => navigate(`/assets/${row.asset_id}`)}
            initialSort={{ key: 'cost_exposure', direction: 'desc' }}
            emptyTitle="No APM results yet"
            emptyMessage="Results appear once the intelligence layers have completed a pass."
          />
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default ApmPage

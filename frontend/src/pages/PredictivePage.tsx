import { CalendarClock, Loader2, PlayCircle, TrendingUp, Wrench } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

import { ChartCard } from '@/charts/ChartCard'
import { EChart } from '@/charts/EChart'
import { barOption } from '@/charts/options'
import { ErrorState } from '@/components/common/ErrorState'
import { MetricTile } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { DataTable, type Column } from '@/components/data'
import { PageHeader, PageTransition } from '@/components/layout'
import { Badge, Button, Card } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import {
  useMaintenanceSchedule,
  usePredictions,
  usePredictiveSummary,
  usePreventiveSummary,
  useRunIntelligence,
} from '@/hooks/useIntelligence'
import type { PredictiveResult, PreventiveResult } from '@/types'
import { formatDateTime, formatHours, formatRelative, humanise } from '@/utils/format'
import { RISK_LABEL, RISK_TONE } from '@/utils/status'

/**
 * Layer 2 — Predictive Maintenance, with Layer 3 scheduling.
 *
 * The SSOT maps Preventive Maintenance to no page of its own, so its output
 * surfaces here: the failure forecast on the left, the service schedule it
 * drives on the right. Presenting them together is what makes the pair
 * actionable — a prediction without a window is an anxiety, not a plan.
 */
export function PredictivePage() {
  const navigate = useNavigate()
  const predictions = usePredictions()
  const summary = usePredictiveSummary()
  const maintenance = useMaintenanceSchedule(true)
  const maintenanceSummary = usePreventiveSummary()
  const run = useRunIntelligence('predictive')

  const predictionColumns = useMemo<Column<PredictiveResult>[]>(
    () => [
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
        key: 'risk_level',
        header: 'Risk',
        accessor: (row) => row.risk_level,
        render: (row) => (
          <Badge tone={RISK_TONE[row.risk_level]} size="sm">
            {RISK_LABEL[row.risk_level]}
          </Badge>
        ),
      },
      {
        key: 'failure_probability',
        header: 'Probability',
        accessor: (row) => row.failure_probability,
        align: 'right',
        render: (row) => (
          <span className="tabular text-sm font-semibold text-foreground">
            {(row.failure_probability * 100).toFixed(0)}%
          </span>
        ),
      },
      {
        key: 'rul',
        header: 'Remaining life',
        accessor: (row) => row.remaining_useful_life_hours ?? Number.MAX_SAFE_INTEGER,
        align: 'right',
        render: (row) => (
          <span className="tabular text-sm text-muted">
            {row.remaining_useful_life_hours === null ||
            row.remaining_useful_life_hours === undefined
              ? 'Stable'
              : formatHours(row.remaining_useful_life_hours)}
          </span>
        ),
        hideBelow: 'sm',
      },
      {
        key: 'predicted_failure_at',
        header: 'Forecast',
        accessor: (row) => row.predicted_failure_at ?? '',
        render: (row) => (
          <span className="text-xs whitespace-nowrap text-muted">
            {row.predicted_failure_at ? formatRelative(row.predicted_failure_at) : '—'}
          </span>
        ),
        hideBelow: 'md',
      },
      {
        key: 'confidence',
        header: 'Confidence',
        accessor: (row) => row.confidence,
        align: 'right',
        render: (row) => (
          <span className="tabular text-sm text-subtle">
            {(row.confidence * 100).toFixed(0)}%
          </span>
        ),
        hideBelow: 'lg',
      },
    ],
    [],
  )

  /** Top assets by failure probability, for the comparison chart. */
  const riskChart = useMemo(() => {
    const top = (predictions.data ?? []).slice(0, 8)
    return {
      categories: top.map((item) => item.asset_code ?? '—'),
      values: top.map((item) => Number((item.failure_probability * 100).toFixed(1))),
    }
  }, [predictions.data])

  if (predictions.isError) {
    return (
      <PageTransition>
        <ErrorState error={predictions.error} onRetry={() => void predictions.refetch()} />
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.predictive.title}
          description={STRINGS.predictive.subtitle}
          icon={TrendingUp}
          layer={2}
          actions={
            <Button
              variant="primary"
              size="sm"
              onClick={() => run.mutate()}
              disabled={run.isPending}
            >
              {run.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <PlayCircle className="size-4" />
              )}
              {STRINGS.predictive.runAction}
            </Button>
          }
        />

        <Section stagger>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Assets at risk"
              value={summary.data?.assets_at_risk ?? null}
              icon={TrendingUp}
              tone={summary.data?.severe ? 'critical' : 'warning'}
              caption={`${summary.data?.severe ?? 0} severe · ${summary.data?.high ?? 0} high`}
            />
            <MetricTile
              label="Mean probability"
              value={
                summary.data
                  ? Number((summary.data.average_failure_probability * 100).toFixed(1))
                  : null
              }
              unit="%"
              precision={1}
              tone="primary"
              caption="Across assessed assets"
            />
            <MetricTile
              label="Soonest failure"
              value={summary.data?.shortest_rul_hours ?? null}
              unit="h"
              precision={0}
              tone="warning"
              caption={
                summary.data?.next_predicted_failure_at
                  ? formatDateTime(summary.data.next_predicted_failure_at)
                  : 'None forecast'
              }
            />
            <MetricTile
              label="Maintenance due"
              value={maintenanceSummary.data?.due_now ?? null}
              icon={Wrench}
              tone={maintenanceSummary.data?.severe_priority ? 'critical' : 'healthy'}
              caption={`${maintenanceSummary.data?.due_this_week ?? 0} due this week`}
            />
          </div>
        </Section>

        <Section title="Risk profile" stagger={false}>
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Highest Failure Probability"
              description="The assets most likely to fail, by forecast likelihood"
              icon={TrendingUp}
              loading={predictions.isLoading}
              empty={riskChart.categories.length === 0}
              emptyMessage="No predictions computed yet."
            >
              <EChart
                height={300}
                deps={[riskChart.categories.join()]}
                buildOption={(theme) =>
                  barOption(theme, riskChart.categories, riskChart.values, {
                    unit: '%',
                    tone: 'warning',
                    max: 100,
                  })
                }
                ariaLabel="Failure probability by asset"
              />
            </ChartCard>

            {/* Layer 3 output, surfaced inside Layer 2's page. */}
            <ChartCard
              title="Service Schedule"
              description="Layer 3 — maintenance recommended before failure"
              icon={CalendarClock}
              loading={maintenance.isLoading}
              empty={(maintenance.data ?? []).length === 0}
              emptyMessage="Nothing is due for service."
              height={300}
            >
              <ul className="max-h-[300px] space-y-2 overflow-y-auto px-3">
                {(maintenance.data ?? []).slice(0, 8).map((item: PreventiveResult) => (
                  <li key={item.id}>
                    <Card
                      elevation="flat"
                      interactive
                      onClick={() => navigate(`/assets/${item.asset_id}`)}
                      className="flex items-center gap-3 p-3"
                    >
                      <Badge tone={RISK_TONE[item.priority]} size="sm" className="shrink-0">
                        {RISK_LABEL[item.priority]}
                      </Badge>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-foreground">
                          {item.task}
                        </p>
                        <p className="truncate text-xs text-subtle">
                          {item.asset_code} ·{' '}
                          {item.window_start
                            ? `window opens ${formatRelative(item.window_start)}`
                            : 'schedule pending'}
                        </p>
                      </div>
                    </Card>
                  </li>
                ))}
              </ul>
            </ChartCard>
          </div>
        </Section>

        <Section
          title="Failure forecasts"
          description="Every assessed asset with its projected remaining life and the reasoning behind it"
          stagger={false}
        >
          <DataTable
            rows={predictions.data ?? []}
            columns={predictionColumns}
            rowKey={(row) => row.id}
            loading={predictions.isLoading}
            pageSize={12}
            searchPlaceholder="Search by asset or risk level…"
            onRowClick={(row) => navigate(`/assets/${row.asset_id}`)}
            emptyTitle="No predictions yet"
            emptyMessage="Predictions appear once enough telemetry history has accumulated to establish a trend."
          />
        </Section>

        {predictions.data?.[0] ? (
          <Section title="Reasoning" stagger={false}>
            <Card elevation="flat" className="space-y-3 p-6">
              <p className="text-xs font-semibold tracking-wider text-subtle uppercase">
                Highest-risk asset · {predictions.data[0].asset_code}
              </p>
              <p className="text-sm leading-relaxed text-foreground">
                {predictions.data[0].rationale}
              </p>
              {predictions.data[0].dominant_fault_type ? (
                <p className="text-xs text-muted">
                  Dominant fault mode:{' '}
                  <span className="text-foreground">
                    {humanise(predictions.data[0].dominant_fault_type)}
                  </span>
                </p>
              ) : null}
            </Card>
          </Section>
        ) : null}
      </PageSections>
    </PageTransition>
  )
}

export default PredictivePage

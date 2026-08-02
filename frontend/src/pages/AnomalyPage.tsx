import { Loader2, PlayCircle, ShieldAlert } from 'lucide-react'
import { useMemo } from 'react'

import { ChartCard } from '@/charts/ChartCard'
import { EChart } from '@/charts/EChart'
import { donutOption, timelineOption } from '@/charts/options'
import { ErrorState } from '@/components/common/ErrorState'
import { MetricTile } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { DataTable, type Column } from '@/components/data'
import { PageHeader, PageTransition } from '@/components/layout'
import { Badge, Button } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { useAnomalies, useAnomalySummary, useRunIntelligence } from '@/hooks/useIntelligence'
import type { AnomalyResult } from '@/types'
import { formatNumber, formatRelative, humanise } from '@/utils/format'
import { SEVERITY_TONE } from '@/utils/status'

/**
 * Layer 1 — Anomaly Detection.
 *
 * Shows what the envelope and statistical detectors have found, and lets an
 * operator trigger a pass rather than waiting for the interval. Every row
 * carries its evidence — observed value against expected band — because an
 * anomaly the user cannot verify is an anomaly they will not act on.
 */
export function AnomalyPage() {
  const anomalies = useAnomalies(undefined, 200)
  const summary = useAnomalySummary()
  const run = useRunIntelligence('anomaly')

  const columns = useMemo<Column<AnomalyResult>[]>(
    () => [
      {
        key: 'detected_at',
        header: 'Detected',
        accessor: (row) => row.detected_at,
        render: (row) => (
          <span className="text-xs whitespace-nowrap text-muted">
            {formatRelative(row.detected_at)}
          </span>
        ),
        width: '130px',
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
        key: 'fault_type',
        header: 'Fault',
        accessor: (row) => row.fault_type,
        render: (row) => (
          <Badge tone={SEVERITY_TONE[row.severity]} size="sm">
            {humanise(row.fault_type)}
          </Badge>
        ),
      },
      {
        key: 'channel',
        header: 'Channel',
        accessor: (row) => row.channel,
        render: (row) => (
          <span className="font-mono text-xs text-muted">{row.channel}</span>
        ),
        hideBelow: 'md',
      },
      {
        key: 'evidence',
        header: 'Observed / Expected',
        accessor: (row) => row.observed_value ?? 0,
        align: 'right',
        render: (row) => (
          <div className="text-right">
            <p className="tabular text-sm font-semibold text-foreground">
              {formatNumber(row.observed_value, 2)}
            </p>
            <p className="tabular text-[11px] text-subtle">
              {row.expected_min !== null && row.expected_min !== undefined
                ? `${formatNumber(row.expected_min, 2)} – ${formatNumber(row.expected_max, 2)}`
                : `max ${formatNumber(row.expected_max, 2)}`}
            </p>
          </div>
        ),
        hideBelow: 'sm',
      },
      {
        key: 'confidence',
        header: 'Confidence',
        accessor: (row) => row.confidence,
        align: 'right',
        render: (row) => (
          <span className="tabular text-sm text-muted">
            {(row.confidence * 100).toFixed(0)}%
          </span>
        ),
        hideBelow: 'lg',
      },
    ],
    [],
  )

  const distribution = useMemo(() => {
    const data = summary.data
    if (!data) return []
    return [
      { key: 'critical', label: 'Critical', value: data.critical, tone: 'critical' },
      { key: 'warning', label: 'Warning', value: data.warning, tone: 'warning' },
      { key: 'information', label: 'Information', value: data.information, tone: 'primary' },
    ]
  }, [summary.data])

  const timeline = useMemo(
    () =>
      (anomalies.data ?? []).slice(0, 120).map((item) => ({
        time: item.detected_at,
        severity: item.severity,
        label: `${humanise(item.fault_type)} — ${item.asset_code ?? ''}`,
      })),
    [anomalies.data],
  )

  if (anomalies.isError) {
    return (
      <PageTransition>
        <ErrorState error={anomalies.error} onRetry={() => void anomalies.refetch()} />
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.anomaly.title}
          description={STRINGS.anomaly.subtitle}
          icon={ShieldAlert}
          layer={1}
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
              {STRINGS.anomaly.runAction}
            </Button>
          }
        />

        <Section stagger>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Today"
              value={summary.data?.today ?? null}
              icon={ShieldAlert}
              tone="primary"
              caption="Anomalies detected"
            />
            <MetricTile
              label="Critical"
              value={summary.data?.critical ?? null}
              tone="critical"
              caption="Require intervention"
            />
            <MetricTile
              label="Warning"
              value={summary.data?.warning ?? null}
              tone="warning"
              caption="Early indicators"
            />
            <MetricTile
              label="Assets affected"
              value={summary.data?.affected_assets ?? null}
              tone="neutral"
              caption={
                summary.data?.top_fault_type
                  ? `Most common: ${humanise(summary.data.top_fault_type)}`
                  : 'Across the estate'
              }
            />
          </div>
        </Section>

        <Section title="Detection pattern" stagger={false}>
          <div className="grid gap-6 xl:grid-cols-3">
            <ChartCard
              title="Anomaly Timeline"
              description="Detections plotted by time and severity"
              className="xl:col-span-2"
              loading={anomalies.isLoading}
              empty={timeline.length === 0}
              emptyMessage="No anomalies detected in the current window."
            >
              <EChart
                height={280}
                deps={[timeline.length]}
                buildOption={(theme) => timelineOption(theme, timeline)}
                ariaLabel="Anomaly timeline"
              />
            </ChartCard>

            <ChartCard
              title="Severity Mix"
              description="Today's detections by severity"
              loading={summary.isLoading}
              empty={distribution.every((slice) => slice.value === 0)}
            >
              <EChart
                height={280}
                deps={[summary.data?.today]}
                buildOption={(theme) =>
                  donutOption(theme, distribution, {
                    centerValue: String(summary.data?.today ?? 0),
                    centerLabel: 'today',
                  })
                }
                ariaLabel="Anomaly severity distribution"
              />
            </ChartCard>
          </div>
        </Section>

        <Section
          title="Recent detections"
          description="Each row shows the reading that breached and the band it was expected to stay within"
          stagger={false}
        >
          <DataTable
            rows={anomalies.data ?? []}
            columns={columns}
            rowKey={(row) => row.id}
            loading={anomalies.isLoading}
            pageSize={12}
            searchPlaceholder="Search by asset, fault or channel…"
            initialSort={{ key: 'detected_at', direction: 'desc' }}
            emptyTitle="No anomalies recorded"
            emptyMessage="The detectors have found nothing outside expected behaviour."
          />
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default AnomalyPage

import {
  ArrowLeft,
  BellRing,
  Check,
  CircleCheck,
  ExternalLink,
  Gauge,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { MetricRow } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { PageHeader, PageTransition } from '@/components/layout'
import { Badge, Button, Card, Skeleton } from '@/components/ui'
import { ROUTES } from '@/constants/navigation'
import { useAlert, useUpdateAlert } from '@/hooks/useAlerts'
import { useAssetAnomalies } from '@/hooks/useIntelligence'
import { cn } from '@/utils/cn'
import { formatDateTime, formatNumber, formatRelative, humanise } from '@/utils/format'
import { ALERT_STATUS_LABEL, SEVERITY_LABEL, SEVERITY_TONE, toneStyle } from '@/utils/status'

/**
 * Alert detail — the evidence view.
 *
 * The database enforces an integrity chain: every alert references the AI
 * result that raised it, which references the telemetry window that triggered
 * it. This page is where that chain becomes useful — the operator sees the
 * reading, the band it was expected to stay within, and the detection history
 * for the same asset, without leaving the page or taking anything on trust.
 */
export function AlertDetailPage() {
  const { alertId } = useParams<{ alertId: string }>()
  const navigate = useNavigate()
  const alert = useAlert(alertId)
  const update = useUpdateAlert()
  const history = useAssetAnomalies(alert.data?.asset_id, 12)

  if (alert.isError) {
    return (
      <PageTransition>
        <ErrorState error={alert.error} onRetry={() => void alert.refetch()} />
      </PageTransition>
    )
  }

  if (alert.isLoading || !alert.data) {
    return (
      <PageTransition>
        <div className="space-y-6">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-10 w-96 max-w-full" />
          <Skeleton className="h-64 rounded-[20px]" />
        </div>
      </PageTransition>
    )
  }

  const data = alert.data
  const tone = SEVERITY_TONE[data.severity]
  const styles = toneStyle(tone)

  const withinBand =
    data.observed_value !== null &&
    data.observed_value !== undefined &&
    data.expected_max !== null &&
    data.expected_max !== undefined
      ? data.observed_value <= data.expected_max &&
        (data.expected_min === null ||
          data.expected_min === undefined ||
          data.observed_value >= data.expected_min)
      : null

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={data.title}
          description={data.message}
          icon={BellRing}
          trail={[
            { label: 'Alerts', path: ROUTES.alerts },
            { label: data.asset_code ?? 'Alert' },
          ]}
          actions={
            <>
              <Button variant="ghost" size="sm" onClick={() => navigate(ROUTES.alerts)}>
                <ArrowLeft className="size-4" />
                Back to queue
              </Button>

              {data.status === 'active' ? (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={update.isPending}
                  onClick={() => update.mutate({ alertId: data.id, status: 'acknowledged' })}
                >
                  <Check className="size-4" />
                  Acknowledge
                </Button>
              ) : null}

              {data.status !== 'resolved' ? (
                <Button
                  variant="primary"
                  size="sm"
                  disabled={update.isPending}
                  onClick={() => update.mutate({ alertId: data.id, status: 'resolved' })}
                >
                  <CircleCheck className="size-4" />
                  Resolve
                </Button>
              ) : null}
            </>
          }
        />

        <Section stagger={false}>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            {/* Evidence */}
            <Card elevation="secondary" className="space-y-6 p-7">
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone={tone}>{SEVERITY_LABEL[data.severity]}</Badge>
                <Badge tone="neutral">{ALERT_STATUS_LABEL[data.status]}</Badge>
                {data.fault_type ? (
                  <Badge tone="neutral">{humanise(data.fault_type)}</Badge>
                ) : null}
              </div>

              <div>
                <h2 className="font-display text-sm font-semibold text-foreground">
                  Evidence
                </h2>
                <p className="mt-1 text-sm text-muted">
                  The reading that breached, and the range it was expected to remain in.
                </p>
              </div>

              {data.observed_value !== null && data.observed_value !== undefined ? (
                <div className="rounded-[14px] border border-border bg-surface-sunken p-5">
                  <div className="flex flex-wrap items-end justify-between gap-6">
                    <div>
                      <p className="text-[10px] font-semibold tracking-wider text-subtle uppercase">
                        Observed
                      </p>
                      <p
                        className={cn(
                          'tabular font-display text-3xl leading-none font-bold',
                          withinBand === false ? styles.text : 'text-foreground',
                        )}
                      >
                        {formatNumber(data.observed_value, 2)}
                      </p>
                      <p className="mt-1 font-mono text-[11px] text-subtle">
                        {data.channel ?? 'unknown channel'}
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-[10px] font-semibold tracking-wider text-subtle uppercase">
                        Expected range
                      </p>
                      <p className="tabular font-display text-lg font-semibold text-muted">
                        {data.expected_min !== null && data.expected_min !== undefined
                          ? `${formatNumber(data.expected_min, 2)} – ${formatNumber(data.expected_max, 2)}`
                          : `≤ ${formatNumber(data.expected_max, 2)}`}
                      </p>
                    </div>
                  </div>

                  {withinBand === false ? (
                    <p className={cn('mt-4 text-xs', styles.text)}>
                      The reading fell outside the acceptable envelope for this asset type.
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-subtle">
                  This alert carries no numeric evidence — it was raised from a state
                  condition rather than a threshold breach.
                </p>
              )}

              <div className="hairline" />

              <div>
                <h3 className="font-display text-sm font-semibold text-foreground">
                  Detection history for this asset
                </h3>
                {history.isLoading ? (
                  <Skeleton className="mt-3 h-24" />
                ) : (history.data ?? []).length === 0 ? (
                  <p className="mt-2 text-sm text-subtle">
                    No prior detections recorded for this asset.
                  </p>
                ) : (
                  <ul className="mt-3 space-y-2">
                    {(history.data ?? []).slice(0, 6).map((item) => (
                      <li
                        key={item.id}
                        className="flex items-center gap-3 rounded-[10px] border border-border px-3 py-2"
                      >
                        <span
                          className={cn(
                            'size-1.5 shrink-0 rounded-full',
                            toneStyle(SEVERITY_TONE[item.severity]).solid,
                          )}
                        />
                        <span className="min-w-0 flex-1 truncate text-xs text-muted">
                          {humanise(item.fault_type)} on {item.channel}
                        </span>
                        <span className="shrink-0 text-[11px] text-subtle">
                          {formatRelative(item.detected_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>

            {/* Context */}
            <div className="space-y-6">
              <Card elevation="flat" className="p-6">
                <h3 className="font-display text-sm font-semibold text-foreground">
                  Lifecycle
                </h3>
                <div className="mt-3 divide-y divide-border">
                  <MetricRow label="Raised" value={formatDateTime(data.triggered_at)} />
                  <MetricRow
                    label="Acknowledged"
                    value={
                      data.acknowledged_at ? formatDateTime(data.acknowledged_at) : 'Not yet'
                    }
                  />
                  <MetricRow
                    label="Resolved"
                    value={data.resolved_at ? formatDateTime(data.resolved_at) : 'Not yet'}
                  />
                  <MetricRow
                    label="Assigned to"
                    value={data.assigned_to ?? 'Unassigned'}
                  />
                </div>
              </Card>

              <Card elevation="flat" className="p-6">
                <h3 className="font-display text-sm font-semibold text-foreground">
                  Asset
                </h3>
                <p className="mt-2 text-sm text-foreground">{data.asset_name}</p>
                <p className="font-mono text-xs text-subtle">{data.asset_code}</p>

                <Button variant="outline" size="sm" className="mt-4 w-full" asChild>
                  <Link to={`/assets/${data.asset_id}`}>
                    <ExternalLink className="size-3.5" />
                    Open asset detail
                  </Link>
                </Button>
              </Card>

              {data.anomaly_result_id ? (
                <Card elevation="flat" className="p-6">
                  <div className="flex items-start gap-3">
                    <Gauge className="mt-0.5 size-4 shrink-0 text-primary" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground">
                        Traceable to source
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-muted">
                        This alert references the anomaly result that raised it, which in
                        turn references the telemetry window that triggered it.
                      </p>
                      <p className="mt-2 font-mono text-[10px] break-all text-subtle">
                        {data.anomaly_result_id}
                      </p>
                    </div>
                  </div>
                </Card>
              ) : null}
            </div>
          </div>
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default AlertDetailPage

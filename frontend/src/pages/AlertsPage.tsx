import { BellRing, Check, CircleCheck, Filter, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { MetricTile } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { DataTable, type Column } from '@/components/data'
import { PageHeader, PageTransition } from '@/components/layout'
import { Badge, Button } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import {
  useAlertList,
  useAlertSummary,
  useDismissAlert,
  useUpdateAlert,
} from '@/hooks/useAlerts'
import type { Alert, AlertSeverity, AlertStatus } from '@/types'
import { cn } from '@/utils/cn'
import { formatRelative, humanise } from '@/utils/format'
import { ALERT_STATUS_LABEL, SEVERITY_LABEL, SEVERITY_TONE } from '@/utils/status'

/**
 * Alerts — the operator queue.
 *
 * Severity and lifecycle filter **independently**, which is the entire reason
 * they are separate fields. "Show me critical alerts that are still
 * unacknowledged" is the question an operations lead actually asks, and a
 * single combined status field could not answer it.
 */

const SEVERITIES: AlertSeverity[] = ['critical', 'warning', 'information']
const STATUSES: AlertStatus[] = ['active', 'acknowledged', 'resolved']

function FilterChip({
  label,
  active,
  onClick,
  tone = 'neutral',
}: {
  label: string
  active: boolean
  onClick: () => void
  tone?: 'critical' | 'warning' | 'primary' | 'neutral'
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
        active
          ? tone === 'critical'
            ? 'border-critical/30 bg-critical-soft text-critical'
            : tone === 'warning'
              ? 'border-warning/30 bg-warning-soft text-warning'
              : 'border-primary/30 bg-primary-soft text-primary'
          : 'border-border text-muted hover:border-border-strong hover:text-foreground',
      )}
    >
      {label}
    </button>
  )
}

export function AlertsPage() {
  const navigate = useNavigate()
  const [severity, setSeverity] = useState<AlertSeverity | undefined>()
  const [status, setStatus] = useState<AlertStatus | undefined>()

  const summary = useAlertSummary()
  const alerts = useAlertList({
    page: 1,
    page_size: 200,
    ...(severity ? { severity } : {}),
    ...(status ? { status } : {}),
  })

  const update = useUpdateAlert()
  const dismiss = useDismissAlert()

  const columns = useMemo<Column<Alert>[]>(
    () => [
      {
        key: 'severity',
        header: 'Severity',
        accessor: (row) => row.severity,
        width: '120px',
        render: (row) => (
          <Badge tone={SEVERITY_TONE[row.severity]} size="sm">
            {SEVERITY_LABEL[row.severity]}
          </Badge>
        ),
      },
      {
        key: 'title',
        header: 'Alert',
        accessor: (row) => row.title,
        render: (row) => (
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">{row.title}</p>
            <p className="truncate text-xs text-subtle">
              {row.asset_code}
              {row.fault_type ? ` · ${humanise(row.fault_type)}` : ''}
            </p>
          </div>
        ),
      },
      {
        key: 'status',
        header: 'Status',
        accessor: (row) => row.status,
        render: (row) => (
          <span
            className={cn(
              'text-xs font-medium',
              row.status === 'active' ? 'text-foreground' : 'text-subtle',
            )}
          >
            {ALERT_STATUS_LABEL[row.status]}
          </span>
        ),
        hideBelow: 'sm',
      },
      {
        key: 'triggered_at',
        header: 'Raised',
        accessor: (row) => row.triggered_at,
        render: (row) => (
          <span className="text-xs whitespace-nowrap text-muted">
            {formatRelative(row.triggered_at)}
          </span>
        ),
        hideBelow: 'md',
      },
      {
        key: 'actions',
        header: '',
        accessor: () => '',
        sortable: false,
        align: 'right',
        width: '160px',
        render: (row) => (
          <div
            className="flex items-center justify-end gap-1"
            onClick={(event) => event.stopPropagation()}
          >
            {row.status === 'active' ? (
              <Button
                variant="ghost"
                size="icon-sm"
                title={STRINGS.alerts.acknowledge}
                aria-label={STRINGS.alerts.acknowledge}
                disabled={update.isPending}
                onClick={() =>
                  update.mutate({ alertId: row.id, status: 'acknowledged' })
                }
              >
                <Check className="size-3.5" />
              </Button>
            ) : null}

            {row.status !== 'resolved' ? (
              <Button
                variant="ghost"
                size="icon-sm"
                title={STRINGS.alerts.resolve}
                aria-label={STRINGS.alerts.resolve}
                disabled={update.isPending}
                onClick={() => update.mutate({ alertId: row.id, status: 'resolved' })}
              >
                <CircleCheck className="size-3.5" />
              </Button>
            ) : null}

            <Button
              variant="ghost"
              size="icon-sm"
              title={STRINGS.alerts.dismiss}
              aria-label={STRINGS.alerts.dismiss}
              disabled={dismiss.isPending}
              onClick={() => dismiss.mutate(row.id)}
            >
              <Trash2 className="size-3.5 text-critical" />
            </Button>
          </div>
        ),
      },
    ],
    [update, dismiss],
  )

  if (alerts.isError) {
    return (
      <PageTransition>
        <ErrorState error={alerts.error} onRetry={() => void alerts.refetch()} />
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.alerts.title}
          description={STRINGS.alerts.subtitle}
          icon={BellRing}
          layer={1}
        />

        <Section stagger>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="Active"
              value={summary.data?.active ?? null}
              icon={BellRing}
              tone={summary.data?.active ? 'warning' : 'healthy'}
              caption="Awaiting acknowledgement"
            />
            <MetricTile
              label="Critical"
              value={summary.data?.critical ?? null}
              tone="critical"
              caption="Immediate attention"
            />
            <MetricTile
              label="Acknowledged"
              value={summary.data?.acknowledged ?? null}
              tone="primary"
              caption="Being worked"
            />
            <MetricTile
              label="Resolved"
              value={summary.data?.resolved ?? null}
              tone="healthy"
              caption="Closed out"
            />
          </div>
        </Section>

        <Section
          title="Queue"
          description="Severity and lifecycle are independent — filter by either or both"
          stagger={false}
          action={
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-1.5">
                <Filter className="size-3.5 text-subtle" />
                <span className="text-[11px] font-semibold tracking-wider text-subtle uppercase">
                  Severity
                </span>
                <div className="ml-1 flex gap-1.5">
                  <FilterChip
                    label="All"
                    active={!severity}
                    onClick={() => setSeverity(undefined)}
                  />
                  {SEVERITIES.map((value) => (
                    <FilterChip
                      key={value}
                      label={SEVERITY_LABEL[value]}
                      active={severity === value}
                      tone={SEVERITY_TONE[value] as 'critical' | 'warning' | 'primary'}
                      onClick={() => setSeverity(severity === value ? undefined : value)}
                    />
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-semibold tracking-wider text-subtle uppercase">
                  Lifecycle
                </span>
                <div className="ml-1 flex gap-1.5">
                  <FilterChip
                    label="All"
                    active={!status}
                    onClick={() => setStatus(undefined)}
                  />
                  {STATUSES.map((value) => (
                    <FilterChip
                      key={value}
                      label={ALERT_STATUS_LABEL[value]}
                      active={status === value}
                      tone="primary"
                      onClick={() => setStatus(status === value ? undefined : value)}
                    />
                  ))}
                </div>
              </div>
            </div>
          }
        >
          <DataTable
            rows={alerts.data?.items ?? []}
            columns={columns}
            rowKey={(row) => row.id}
            loading={alerts.isLoading}
            pageSize={14}
            searchPlaceholder="Search alerts by title, asset or fault…"
            onRowClick={(row) => navigate(`/alerts/${row.id}`)}
            initialSort={{ key: 'triggered_at', direction: 'desc' }}
            emptyTitle="No alerts"
            emptyMessage="Nothing has breached its expected envelope. The fleet is operating cleanly."
          />
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default AlertsPage

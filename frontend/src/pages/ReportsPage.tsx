import {
  Activity,
  Download,
  FileBarChart,
  FileJson,
  Loader2,
  Table2,
  Wrench,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'

import { ErrorState } from '@/components/common/ErrorState'
import { PageSections, Section } from '@/components/common/Section'
import { PageHeader, PageTransition } from '@/components/layout'
import { Button, Card, Skeleton } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { useExportReport, useReports } from '@/hooks/usePlatform'
import type { ReportDefinition } from '@/types'
import { cn } from '@/utils/cn'

/**
 * Report centre.
 *
 * CSV and JSON are generated natively by the platform. PDF and spreadsheet
 * rendering belong to the reporting phase and are deliberately absent rather
 * than stubbed — an export button that produces an empty or fabricated
 * document is worse than one that is not there, particularly for records
 * someone may forward to a regulator.
 */

const REPORT_ICONS: Record<string, LucideIcon> = {
  energy: Zap,
  health: Activity,
  maintenance: Wrench,
  telemetry: Table2,
}

const RANGES = [
  { label: 'Last 24 hours', minutes: 1440 },
  { label: 'Last 7 days', minutes: 10_080 },
  { label: 'Last 30 days', minutes: 43_200 },
]

function ReportCard({ report }: { report: ReportDefinition }) {
  const [range, setRange] = useState(RANGES[0].minutes)
  const exportReport = useExportReport()
  const Icon = REPORT_ICONS[report.key] ?? FileBarChart

  const busy = exportReport.isPending

  return (
    <Card elevation="secondary" className="flex h-full flex-col gap-5 p-6">
      <div className="flex items-start gap-3.5">
        <span className="grid size-11 shrink-0 place-items-center rounded-[12px] border border-border bg-surface-sunken text-primary">
          <Icon className="size-5" />
        </span>
        <div className="min-w-0">
          <h3 className="font-display text-base font-semibold text-foreground">
            {report.name}
          </h3>
          <p className="mt-1 text-sm leading-relaxed text-muted">{report.description}</p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-[10px] font-semibold tracking-wider text-subtle uppercase">
          Columns
        </p>
        <div className="flex flex-wrap gap-1.5">
          {report.columns.slice(0, 6).map((column) => (
            <span
              key={column}
              className="rounded-md border border-border px-1.5 py-0.5 font-mono text-[10px] text-subtle"
            >
              {column}
            </span>
          ))}
          {report.columns.length > 6 ? (
            <span className="px-1 py-0.5 text-[10px] text-subtle">
              +{report.columns.length - 6}
            </span>
          ) : null}
        </div>
      </div>

      {report.key === 'telemetry' ? (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold tracking-wider text-subtle uppercase">
            Window
          </p>
          <div className="flex flex-wrap gap-1.5">
            {RANGES.map((option) => (
              <button
                key={option.minutes}
                type="button"
                onClick={() => setRange(option.minutes)}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors',
                  range === option.minutes
                    ? 'border-primary/30 bg-primary-soft text-primary'
                    : 'border-border text-muted hover:border-border-strong hover:text-foreground',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-auto flex gap-2 pt-2">
        <Button
          variant="primary"
          size="sm"
          className="flex-1"
          disabled={busy}
          onClick={() =>
            exportReport.mutate({ report: report.key, format: 'csv', minutes: range })
          }
        >
          {busy ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Download className="size-4" />
          )}
          CSV
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          disabled={busy}
          onClick={() =>
            exportReport.mutate({ report: report.key, format: 'json', minutes: range })
          }
        >
          <FileJson className="size-4" />
          JSON
        </Button>
      </div>

      {exportReport.isError ? (
        <ErrorState error={exportReport.error} compact />
      ) : null}
    </Card>
  )
}

export function ReportsPage() {
  const reports = useReports()

  if (reports.isError) {
    return (
      <PageTransition>
        <ErrorState error={reports.error} onRetry={() => void reports.refetch()} />
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.reports.title}
          description={STRINGS.reports.subtitle}
          icon={FileBarChart}
        />

        <Section
          title="Available reports"
          description="Generated from live platform records at the moment you export"
        >
          {reports.isLoading ? (
            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-72 rounded-[20px]" />
              ))}
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
              {(reports.data ?? []).map((report) => (
                <ReportCard key={report.key} report={report} />
              ))}
            </div>
          )}
        </Section>

        <Section stagger={false}>
          <Card elevation="flat" className="p-6">
            <h3 className="font-display text-sm font-semibold text-foreground">
              Formats
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
              CSV and JSON are produced natively by the platform. PDF and spreadsheet
              rendering arrive with the reporting phase — they are absent here rather
              than stubbed, because an export that yields an empty or fabricated document
              is worse than one that does not exist.
            </p>
          </Card>
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default ReportsPage

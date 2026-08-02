import type { HTMLAttributes } from 'react'

import { cn } from '@/utils/cn'

/**
 * Skeleton placeholder.
 *
 * The design system bans spinners outright, so every loading state in the
 * platform is built from these. A skeleton preserves layout, which means the
 * page does not jump when data arrives — the single biggest cause of a
 * dashboard feeling cheap.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('skeleton', className)} aria-hidden {...props} />
}

/** Skeleton shaped like a KPI card, so the grid does not reflow on load. */
export function KpiSkeleton() {
  return (
    <div className="glass-panel space-y-4 p-6">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-9 w-32" />
      <Skeleton className="h-3 w-20" />
    </div>
  )
}

/** Skeleton shaped like a chart panel. */
export function ChartSkeleton({ height = 260 }: { height?: number }) {
  return (
    <div className="glass-panel space-y-4 p-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-16" />
      </div>
      <Skeleton className="w-full rounded-[12px]" style={{ height }} />
    </div>
  )
}

/** Skeleton shaped like a table. */
export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-6">
      <Skeleton className="h-9 w-full" />
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="h-12 w-full opacity-[calc(1-var(--i)*0.06)]" />
      ))}
    </div>
  )
}

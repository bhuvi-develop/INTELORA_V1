import { forwardRef, type HTMLAttributes, type TdHTMLAttributes, type ThHTMLAttributes } from 'react'

import { cn } from '@/utils/cn'

/**
 * Table primitives.
 *
 * Tables sit in the minimal effect tier: row hover changes colour and nothing
 * else. A table row that lifts or glows is unreadable when scanning, which is
 * the only thing a table is for.
 *
 * The header is sticky by default because these tables show telemetry, and
 * telemetry tables get long.
 */

export const Table = forwardRef<HTMLTableElement, HTMLAttributes<HTMLTableElement>>(
  function Table({ className, ...props }, ref) {
    return (
      <div className="scroll-x w-full">
        <table
          ref={ref}
          className={cn('w-full caption-bottom border-collapse text-sm', className)}
          {...props}
        />
      </div>
    )
  },
)

export const TableHeader = forwardRef<
  HTMLTableSectionElement,
  HTMLAttributes<HTMLTableSectionElement>
>(function TableHeader({ className, ...props }, ref) {
  return (
    <thead
      ref={ref}
      className={cn(
        'sticky top-0 z-10 bg-surface-sunken/95 backdrop-blur-sm',
        '[&_tr]:border-b [&_tr]:border-border',
        className,
      )}
      {...props}
    />
  )
})

export const TableBody = forwardRef<
  HTMLTableSectionElement,
  HTMLAttributes<HTMLTableSectionElement>
>(function TableBody({ className, ...props }, ref) {
  return (
    <tbody
      ref={ref}
      className={cn('[&_tr:last-child]:border-0', className)}
      {...props}
    />
  )
})

export const TableRow = forwardRef<
  HTMLTableRowElement,
  HTMLAttributes<HTMLTableRowElement> & { interactive?: boolean }
>(function TableRow({ className, interactive, ...props }, ref) {
  return (
    <tr
      ref={ref}
      className={cn(
        'lift-none border-b border-border',
        'hover:bg-surface-sunken/60',
        interactive && 'cursor-pointer',
        className,
      )}
      {...props}
    />
  )
})

export const TableHead = forwardRef<
  HTMLTableCellElement,
  ThHTMLAttributes<HTMLTableCellElement>
>(function TableHead({ className, ...props }, ref) {
  return (
    <th
      ref={ref}
      className={cn(
        'h-11 px-4 text-left align-middle',
        'text-[11px] font-semibold tracking-wider text-subtle uppercase',
        'whitespace-nowrap',
        className,
      )}
      {...props}
    />
  )
})

export const TableCell = forwardRef<
  HTMLTableCellElement,
  TdHTMLAttributes<HTMLTableCellElement>
>(function TableCell({ className, ...props }, ref) {
  return (
    <td
      ref={ref}
      className={cn('px-4 py-3 align-middle text-foreground', className)}
      {...props}
    />
  )
})

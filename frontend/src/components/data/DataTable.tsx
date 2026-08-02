import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import type { ReactNode } from 'react'

import { EmptyState } from '@/components/common/EmptyState'
import {
  Button,
  Card,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableSkeleton,
} from '@/components/ui'
import { useDataTable, type Column } from '@/hooks/useDataTable'
import { cn } from '@/utils/cn'

/**
 * Enterprise data table.
 *
 * Search, sort, pagination and a sticky header, with the empty, filtered-empty
 * and loading states handled here rather than by each caller.
 *
 * Tables are the minimal effect tier: rows change colour on hover and nothing
 * moves. A row that lifts is unreadable while scanning, which is the only
 * thing a table is for.
 *
 * State is shaped to match what the collection endpoints already accept —
 * page, page size, sort key, direction, search — so moving a table onto the
 * server is a change of data source, not a rewrite. Telemetry retention is
 * unlimited, so some of these tables will need that move.
 */

const HIDE_BELOW: Record<NonNullable<Column<unknown>['hideBelow']>, string> = {
  sm: 'hidden sm:table-cell',
  md: 'hidden md:table-cell',
  lg: 'hidden lg:table-cell',
}

interface DataTableProps<T> {
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string
  loading?: boolean
  pageSize?: number
  searchPlaceholder?: string
  /** Rendered beside the search field: filters, exports, actions. */
  toolbar?: ReactNode
  onRowClick?: (row: T) => void
  emptyTitle?: string
  emptyMessage?: string
  initialSort?: { key: string; direction: 'asc' | 'desc' }
  className?: string
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  loading = false,
  pageSize = 10,
  searchPlaceholder = 'Search…',
  toolbar,
  onRowClick,
  emptyTitle,
  emptyMessage,
  initialSort,
  className,
}: DataTableProps<T>) {
  const table = useDataTable({ rows, columns, pageSize, initialSort })

  return (
    <Card elevation="flat" className={cn('overflow-hidden', className)}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
        <div className="min-w-52 flex-1">
          <Input
            value={table.search}
            onChange={(event) => table.setSearch(event.target.value)}
            placeholder={searchPlaceholder}
            icon={<Search />}
            aria-label="Search table"
          />
        </div>
        {toolbar}
        <span className="tabular ml-auto text-xs whitespace-nowrap text-subtle">
          {table.totalRows} {table.totalRows === 1 ? 'record' : 'records'}
        </span>
      </div>

      {/* Body */}
      {loading ? (
        <TableSkeleton rows={Math.min(pageSize, 6)} />
      ) : table.isEmpty ? (
        <EmptyState variant="default" title={emptyTitle} message={emptyMessage} />
      ) : table.hasNoMatches ? (
        <EmptyState variant="noResults" />
      ) : (
        <div className="max-h-[640px] overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                {columns.map((column) => {
                  const sorted = table.sortKey === column.key
                  return (
                    <TableHead
                      key={column.key}
                      style={column.width ? { width: column.width } : undefined}
                      className={cn(
                        column.align === 'right' && 'text-right',
                        column.align === 'center' && 'text-center',
                        column.hideBelow && HIDE_BELOW[column.hideBelow],
                      )}
                    >
                      {column.sortable === false ? (
                        column.header
                      ) : (
                        <button
                          type="button"
                          onClick={() => table.toggleSort(column.key)}
                          className={cn(
                            'inline-flex items-center gap-1.5 transition-colors hover:text-foreground',
                            sorted && 'text-foreground',
                            column.align === 'right' && 'flex-row-reverse',
                          )}
                          aria-label={`Sort by ${column.header}`}
                        >
                          {column.header}
                          {sorted ? (
                            table.sortDirection === 'asc' ? (
                              <ArrowUp className="size-3" />
                            ) : (
                              <ArrowDown className="size-3" />
                            )
                          ) : null}
                        </button>
                      )}
                    </TableHead>
                  )
                })}
              </TableRow>
            </TableHeader>

            <TableBody>
              {table.rows.map((row) => (
                <TableRow
                  key={rowKey(row)}
                  interactive={Boolean(onRowClick)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((column) => (
                    <TableCell
                      key={column.key}
                      className={cn(
                        column.align === 'right' && 'text-right tabular',
                        column.align === 'center' && 'text-center',
                        column.hideBelow && HIDE_BELOW[column.hideBelow],
                      )}
                    >
                      {column.render ? column.render(row) : (column.accessor(row) ?? '—')}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      {!loading && table.totalPages > 1 ? (
        <div className="flex items-center justify-between gap-4 border-t border-border p-4">
          <p className="tabular text-xs text-subtle">
            Page {table.page} of {table.totalPages}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={table.page <= 1}
              onClick={() => table.setPage(table.page - 1)}
              aria-label="Previous page"
            >
              <ChevronLeft className="size-4" />
              Previous
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={table.page >= table.totalPages}
              onClick={() => table.setPage(table.page + 1)}
              aria-label="Next page"
            >
              Next
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      ) : null}
    </Card>
  )
}

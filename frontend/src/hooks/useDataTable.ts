import { useCallback, useMemo, useState } from 'react'

import type { SortDirection } from '@/types'

export interface Column<T> {
  key: string
  header: string
  /** Extract the sortable/searchable primitive for a row. */
  accessor: (row: T) => string | number | null | undefined
  /** Custom cell renderer. Falls back to the accessor value. */
  render?: (row: T) => React.ReactNode
  sortable?: boolean
  align?: 'left' | 'right' | 'center'
  /** Hidden below the large breakpoint, keeping narrow viewports readable. */
  hideBelow?: 'sm' | 'md' | 'lg'
  width?: string
}

interface DataTableOptions<T> {
  rows: T[]
  columns: Column<T>[]
  pageSize?: number
  initialSort?: { key: string; direction: SortDirection }
}

/**
 * Client-side table state: search, sort, pagination.
 *
 * The shape of this hook deliberately mirrors what a server-side
 * implementation needs — page, page size, sort key, sort direction, search
 * term. Collection endpoints already accept exactly those parameters, so
 * moving a table onto the server is a matter of swapping the data source, not
 * rewriting the component. Retention is unlimited, so several of these tables
 * will need that move.
 */
export function useDataTable<T>({
  rows,
  columns,
  pageSize: initialPageSize = 10,
  initialSort,
}: DataTableOptions<T>) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(initialPageSize)
  const [sortKey, setSortKey] = useState<string | null>(initialSort?.key ?? null)
  const [sortDirection, setSortDirection] = useState<SortDirection>(
    initialSort?.direction ?? 'asc',
  )

  const columnMap = useMemo(
    () => new Map(columns.map((column) => [column.key, column])),
    [columns],
  )

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return rows

    return rows.filter((row) =>
      columns.some((column) => {
        const value = column.accessor(row)
        return value !== null && value !== undefined
          ? String(value).toLowerCase().includes(term)
          : false
      }),
    )
  }, [rows, columns, search])

  const sorted = useMemo(() => {
    if (!sortKey) return filtered
    const column = columnMap.get(sortKey)
    if (!column) return filtered

    const factor = sortDirection === 'asc' ? 1 : -1

    return [...filtered].sort((a, b) => {
      const left = column.accessor(a)
      const right = column.accessor(b)

      // Missing values sort last in either direction: a blank cell is not
      // "smaller" than a real reading, it is simply absent.
      if (left === null || left === undefined) return 1
      if (right === null || right === undefined) return -1

      if (typeof left === 'number' && typeof right === 'number') {
        return (left - right) * factor
      }
      return String(left).localeCompare(String(right)) * factor
    })
  }, [filtered, sortKey, sortDirection, columnMap])

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize))
  const safePage = Math.min(page, totalPages)

  const paged = useMemo(
    () => sorted.slice((safePage - 1) * pageSize, safePage * pageSize),
    [sorted, safePage, pageSize],
  )

  const toggleSort = useCallback(
    (key: string) => {
      setSortKey((current) => {
        if (current === key) {
          setSortDirection((direction) => (direction === 'asc' ? 'desc' : 'asc'))
          return current
        }
        setSortDirection('asc')
        return key
      })
      setPage(1)
    },
    [],
  )

  const updateSearch = useCallback((value: string) => {
    setSearch(value)
    setPage(1)
  }, [])

  return {
    rows: paged,
    allRows: sorted,
    search,
    setSearch: updateSearch,
    page: safePage,
    setPage,
    pageSize,
    setPageSize,
    totalPages,
    totalRows: sorted.length,
    sortKey,
    sortDirection,
    toggleSort,
    isEmpty: rows.length === 0,
    isFiltered: search.trim().length > 0,
    hasNoMatches: rows.length > 0 && sorted.length === 0,
  }
}

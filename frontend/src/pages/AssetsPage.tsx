import { Boxes } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { MetricTile } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import {
  ConnectivityPill,
  HealthPill,
  OperationalPill,
} from '@/components/common/StatusPill'
import { DataTable, type Column } from '@/components/data'
import { PageHeader, PageTransition } from '@/components/layout'
import { Button } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { useAssetBusinessModels } from '@/hooks/useAssets'
import type { AssetBusinessModel, AssetType, HealthState } from '@/types'
import { cn } from '@/utils/cn'
import { formatCurrency, formatMetric, formatPercent, humanise } from '@/utils/format'

/**
 * Asset registry.
 *
 * Bound to the unified business model, so one table renders every category
 * despite their reporting different channels. Values a category does not
 * report show as an em dash rather than zero.
 *
 * Filters arrive as query parameters, which is what makes the Cockpit's KPI
 * cards work as entry points: "Warning" navigates here pre-filtered rather
 * than to a generic list the user then has to narrow themselves.
 */

const ASSET_TYPE_LABEL: Record<AssetType, string> = {
  laptop_charger: 'Laptop Chargers',
  mobile_charger: 'Mobile Chargers',
  air_conditioner: 'Air Conditioners',
}

export function AssetsPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()

  const assetType = (params.get('asset_type') as AssetType | null) ?? undefined
  const health = (params.get('health') as HealthState | null) ?? undefined

  const assets = useAssetBusinessModels(assetType, health)

  const stats = useMemo(() => {
    const rows = assets.data ?? []
    return {
      total: rows.length,
      healthy: rows.filter((row) => row.health_state === 'healthy').length,
      warning: rows.filter((row) => row.health_state === 'warning').length,
      critical: rows.filter((row) => row.health_state === 'critical').length,
    }
  }, [assets.data])

  const columns = useMemo<Column<AssetBusinessModel>[]>(
    () => [
      {
        key: 'name',
        header: 'Asset',
        accessor: (row) => row.name,
        render: (row) => (
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">{row.name}</p>
            <p className="font-mono text-[11px] text-subtle">{row.asset_code}</p>
          </div>
        ),
      },
      {
        key: 'asset_type',
        header: 'Category',
        accessor: (row) => row.asset_type,
        render: (row) => (
          <span className="text-xs text-muted">{humanise(row.asset_type)}</span>
        ),
        hideBelow: 'md',
      },
      {
        key: 'health_state',
        header: 'Health',
        accessor: (row) => row.health_score,
        render: (row) => (
          <HealthPill state={row.health_state} score={row.health_score} />
        ),
      },
      {
        key: 'operational_state',
        header: 'Operation',
        accessor: (row) => row.operational_state,
        render: (row) => <OperationalPill state={row.operational_state} />,
        hideBelow: 'sm',
      },
      {
        key: 'connectivity_state',
        header: 'Link',
        accessor: (row) => row.connectivity_state,
        render: (row) => <ConnectivityPill state={row.connectivity_state} />,
        hideBelow: 'lg',
      },
      {
        key: 'power_w',
        header: 'Power',
        accessor: (row) => row.power_w ?? -1,
        align: 'right',
        render: (row) => (
          <span className="text-sm text-foreground">
            {formatMetric(row.power_w, 'W', 1)}
          </span>
        ),
      },
      {
        key: 'energy_kwh',
        header: 'Energy today',
        accessor: (row) => row.energy_kwh ?? -1,
        align: 'right',
        render: (row) => (
          <span
            className={cn(
              'text-sm',
              row.energy_kwh === null || row.energy_kwh === undefined
                ? 'text-subtle/60'
                : 'text-foreground',
            )}
            title={
              row.energy_kwh === null || row.energy_kwh === undefined
                ? 'This asset category has no energy meter'
                : undefined
            }
          >
            {formatMetric(row.energy_kwh, 'kWh', 3)}
          </span>
        ),
        hideBelow: 'md',
      },
      {
        key: 'efficiency',
        header: 'Efficiency',
        accessor: (row) => row.efficiency,
        align: 'right',
        render: (row) => (
          <span className="text-sm text-muted">{formatPercent(row.efficiency, 0)}</span>
        ),
        hideBelow: 'lg',
      },
      {
        key: 'business_score',
        header: 'Business score',
        accessor: (row) => row.business_score,
        align: 'right',
        render: (row) => (
          <span className="text-sm font-semibold text-foreground">
            {row.business_score.toFixed(0)}
          </span>
        ),
      },
      {
        key: 'cost',
        header: 'Cost rate',
        accessor: (row) => row.cost,
        align: 'right',
        render: (row) => (
          <span className="text-sm text-muted" title="Operating cost per hour at current draw">
            {formatCurrency(row.cost, 'USD', 3)}/h
          </span>
        ),
        hideBelow: 'lg',
      },
    ],
    [],
  )

  const setFilter = (key: string, value?: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  if (assets.isError) {
    return (
      <PageTransition>
        <ErrorState error={assets.error} onRetry={() => void assets.refetch()} />
      </PageTransition>
    )
  }

  const activeFilters = [
    assetType ? ASSET_TYPE_LABEL[assetType] : null,
    health ? `${health} health` : null,
  ].filter(Boolean)

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.assets.title}
          description={
            activeFilters.length
              ? `Filtered to ${activeFilters.join(' · ')}`
              : STRINGS.assets.subtitle
          }
          icon={Boxes}
          actions={
            activeFilters.length ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setParams(new URLSearchParams(), { replace: true })}
              >
                Clear filters
              </Button>
            ) : null
          }
        />

        <Section stagger>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricTile
              label="In scope"
              value={stats.total}
              icon={Boxes}
              tone="primary"
              caption={activeFilters.length ? 'Matching filters' : 'Total assets'}
            />
            <MetricTile label="Healthy" value={stats.healthy} tone="healthy" />
            <MetricTile label="Warning" value={stats.warning} tone="warning" />
            <MetricTile label="Critical" value={stats.critical} tone="critical" />
          </div>
        </Section>

        <Section
          title="Registry"
          description="Every asset on the unified business model — a dash means the category does not report that channel"
          stagger={false}
          action={
            <div className="flex flex-wrap gap-1.5">
              {(Object.keys(ASSET_TYPE_LABEL) as AssetType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setFilter('asset_type', assetType === type ? undefined : type)}
                  className={cn(
                    'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                    assetType === type
                      ? 'border-primary/30 bg-primary-soft text-primary'
                      : 'border-border text-muted hover:border-border-strong hover:text-foreground',
                  )}
                >
                  {ASSET_TYPE_LABEL[type]}
                </button>
              ))}
            </div>
          }
        >
          <DataTable
            rows={assets.data ?? []}
            columns={columns}
            rowKey={(row) => row.asset_id}
            loading={assets.isLoading}
            pageSize={15}
            searchPlaceholder="Search by name or asset code…"
            onRowClick={(row) => navigate(`/assets/${row.asset_id}`)}
            initialSort={{ key: 'business_score', direction: 'asc' }}
            emptyTitle="No assets registered"
            emptyMessage="Assets appear here once the platform has a registry to monitor."
          />
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default AssetsPage

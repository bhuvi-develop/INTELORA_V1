import { ArrowLeft, Boxes, Cpu, MapPin, Thermometer, Zap } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ChartCard } from '@/charts/ChartCard'
import { EChart } from '@/charts/EChart'
import { lineOption } from '@/charts/options'
import { ErrorState } from '@/components/common/ErrorState'
import { MetricRow, MetricTile } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { StatusTriple } from '@/components/common/StatusPill'
import { PageHeader, PageTransition } from '@/components/layout'
import { Badge, Button, Card, Skeleton } from '@/components/ui'
import { ROUTES } from '@/constants/navigation'
import { useAsset, useAssetBusiness, useAssetTelemetry } from '@/hooks/useAssets'
import { useAssetAnomalies } from '@/hooks/useIntelligence'
import { useTelemetryHistory } from '@/hooks/usePlatform'
import type { AssetCapabilities } from '@/types'
import {
  NOT_REPORTED,
  formatCurrency,
  formatDateTime,
  formatHours,
  formatMetric,
  formatPercent,
  formatRelative,
  humanise,
} from '@/utils/format'
import { LIFECYCLE_LABEL, LIFECYCLE_TONE, SEVERITY_TONE } from '@/utils/status'

/**
 * Asset detail.
 *
 * The one place in the platform where asset-specific telemetry is shown
 * directly rather than through the business model — because this *is* the
 * device view. Which channels appear is driven by the category's declared
 * capabilities, so an air conditioner shows relay state and power factor while
 * a mobile charger shows neither, with no branching on asset type anywhere in
 * this file.
 */

/** Channels to chart, in the order they matter, gated by capability. */
const CHANNELS: Array<{
  key: string
  capability: keyof AssetCapabilities
  label: string
}> = [
  { key: 'power_w', capability: 'power', label: 'Power' },
  { key: 'temperature_c', capability: 'temperature', label: 'Temperature' },
  { key: 'voltage_v', capability: 'voltage', label: 'Voltage' },
  { key: 'current_a', capability: 'current', label: 'Current' },
  { key: 'power_factor', capability: 'power_factor', label: 'Power factor' },
  { key: 'energy_kwh', capability: 'energy', label: 'Energy' },
]

export function AssetDetailPage() {
  const { assetId } = useParams<{ assetId: string }>()
  const navigate = useNavigate()

  const asset = useAsset(assetId)
  const business = useAssetBusiness(assetId)
  const anomalies = useAssetAnomalies(assetId, 10)
  // Category-specific channels live on the raw reading, not the business
  // model — keeping them out of that contract is what makes it uniform.
  const telemetry = useAssetTelemetry(assetId)

  const capabilities = asset.data?.capabilities

  // Only request channels this asset actually reports; asking for the rest
  // would return a series of nulls and imply a broken sensor.
  const channels = useMemo(
    () =>
      capabilities
        ? CHANNELS.filter((channel) => capabilities[channel.capability])
        : [],
    [capabilities],
  )

  const history = useTelemetryHistory(
    {
      asset_id: assetId,
      channels: channels.map((channel) => channel.key).join(','),
      minutes: 60,
      points: 180,
    },
    Boolean(assetId && channels.length > 0),
  )

  if (asset.isError) {
    return (
      <PageTransition>
        <ErrorState error={asset.error} onRetry={() => void asset.refetch()} />
      </PageTransition>
    )
  }

  if (asset.isLoading || !asset.data) {
    return (
      <PageTransition>
        <div className="space-y-6">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-10 w-96 max-w-full" />
          <Skeleton className="h-72 rounded-[20px]" />
        </div>
      </PageTransition>
    )
  }

  const data = asset.data
  const model = business.data
  const latest = telemetry.data
  const scope = data.scope

  const primarySeries = history.data?.find((series) => series.key === 'power_w')
  const thermalSeries = history.data?.find((series) => series.key === 'temperature_c')
  const electricalSeries = (history.data ?? []).filter((series) =>
    ['voltage_v', 'current_a'].includes(series.key),
  )
  const factorSeries = history.data?.find((series) => series.key === 'power_factor')

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={data.name}
          description={`${humanise(data.asset_type)} · ${data.manufacturer ?? 'Unknown manufacturer'} ${data.model ?? ''}`}
          icon={Boxes}
          trail={[
            { label: 'Asset Registry', path: ROUTES.assets },
            { label: data.asset_code },
          ]}
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate(ROUTES.assets)}>
              <ArrowLeft className="size-4" />
              Back to registry
            </Button>
          }
        />

        {/* Identity and the three status dimensions. */}
        <Section stagger={false}>
          <Card elevation="primary" className="space-y-6 p-7">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div className="space-y-3">
                <p className="font-mono text-xs text-subtle">{data.asset_code}</p>
                <StatusTriple
                  health={data.health_state}
                  healthScore={data.health_score}
                  operational={data.operational_state}
                  connectivity={data.connectivity_state}
                />
                <Badge tone={LIFECYCLE_TONE[data.lifecycle_stage]} size="sm">
                  {LIFECYCLE_LABEL[data.lifecycle_stage]}
                </Badge>
              </div>

              {scope ? (
                <div className="flex items-start gap-2.5 text-sm">
                  <MapPin className="mt-0.5 size-4 shrink-0 text-subtle" />
                  <div>
                    <p className="text-foreground">{scope.location_name ?? 'Unassigned'}</p>
                    <p className="text-xs text-subtle">
                      {[scope.building, scope.department].filter(Boolean).join(' · ') ||
                        'No department recorded'}
                    </p>
                    {scope.asset_group_name ? (
                      <p className="mt-0.5 text-xs text-subtle">
                        Fleet: {scope.asset_group_name}
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="hairline" />

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricTile
                label="Live power"
                value={model?.power_w ?? null}
                unit="W"
                precision={1}
                icon={Zap}
                tone="primary"
              />
              <MetricTile
                label="Temperature"
                value={model?.temperature_c ?? null}
                unit="°C"
                precision={1}
                icon={Thermometer}
                tone="warning"
              />
              <MetricTile
                label="Efficiency"
                value={model?.efficiency ?? null}
                unit="%"
                precision={1}
                icon={Cpu}
                tone="healthy"
              />
              <MetricTile
                label="Business score"
                value={model?.business_score ?? null}
                precision={0}
                tone="primary"
                caption={`Cost rate ${formatCurrency(model?.cost ?? 0, 'USD', 3)}/h`}
              />
            </div>
          </Card>
        </Section>

        {/* Telemetry — driven by declared capabilities, two charts per row. */}
        <Section
          title="Telemetry"
          description={`Rolling 60-minute window · ${channels.length} channel${channels.length === 1 ? '' : 's'} reported by this category`}
          stagger={false}
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard
              title="Power"
              description="Instantaneous demand"
              icon={Zap}
              loading={history.isLoading}
              empty={!primarySeries?.points.length}
            >
              {primarySeries ? (
                <EChart
                  height={260}
                  deps={[primarySeries.points.length]}
                  buildOption={(theme) => lineOption(theme, [primarySeries])}
                  ariaLabel="Power trend"
                />
              ) : null}
            </ChartCard>

            <ChartCard
              title="Thermal"
              description="Operating temperature"
              icon={Thermometer}
              loading={history.isLoading}
              empty={!thermalSeries?.points.length}
            >
              {thermalSeries ? (
                <EChart
                  height={260}
                  deps={[thermalSeries.points.length]}
                  buildOption={(theme) => lineOption(theme, [thermalSeries])}
                  ariaLabel="Temperature trend"
                />
              ) : null}
            </ChartCard>

            {electricalSeries.length > 0 ? (
              <ChartCard
                title="Electrical"
                description="Voltage and current"
                icon={Cpu}
                loading={history.isLoading}
                empty={electricalSeries.every((series) => series.points.length === 0)}
              >
                <EChart
                  height={260}
                  deps={[electricalSeries.map((s) => s.points.length).join()]}
                  buildOption={(theme) =>
                    lineOption(theme, electricalSeries, { area: false, showLegend: true })
                  }
                  ariaLabel="Voltage and current trends"
                />
              </ChartCard>
            ) : null}

            {factorSeries ? (
              <ChartCard
                title="Power Factor"
                description="Ratio of real to apparent power"
                icon={Cpu}
                loading={history.isLoading}
                empty={!factorSeries.points.length}
              >
                <EChart
                  height={260}
                  deps={[factorSeries.points.length]}
                  buildOption={(theme) => lineOption(theme, [factorSeries])}
                  ariaLabel="Power factor trend"
                />
              </ChartCard>
            ) : null}
          </div>
        </Section>

        <Section stagger={false}>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card elevation="flat" className="p-6">
              <h3 className="font-display text-sm font-semibold text-foreground">
                Nameplate &amp; service
              </h3>
              <div className="mt-3 divide-y divide-border">
                <MetricRow
                  label="Rated power"
                  value={formatMetric(data.rated_power_w, 'W', 0)}
                />
                <MetricRow
                  label="Rated voltage"
                  value={formatMetric(data.rated_voltage_v, 'V', 0)}
                />
                <MetricRow
                  label="Commissioned"
                  value={data.commissioned_at ? formatDateTime(data.commissioned_at) : '—'}
                />
                <MetricRow
                  label="Operating hours"
                  value={formatHours(data.operating_hours)}
                />
                <MetricRow
                  label="Lifetime energy"
                  value={
                    capabilities?.energy
                      ? formatMetric(data.lifetime_energy_kwh, 'kWh', 2)
                      : 'Not metered'
                  }
                />
                {capabilities?.relay ? (
                  <MetricRow
                    label="Relay operations"
                    value={data.relay_operations.toLocaleString()}
                  />
                ) : null}

                {/* Category-specific channels. Rendered from the capability
                    descriptor rather than by branching on asset type, so a new
                    category surfaces its own channels with no change here. */}
                {capabilities?.battery ? (
                  <MetricRow
                    label="Battery"
                    value={formatPercent(latest?.battery_percent, 1)}
                    hint={
                      latest?.charging_state
                        ? humanise(latest.charging_state).toLowerCase()
                        : undefined
                    }
                  />
                ) : null}
                {capabilities?.charge_cycles ? (
                  <MetricRow
                    label="Charge cycles"
                    value={latest?.charge_cycles?.toLocaleString() ?? NOT_REPORTED}
                  />
                ) : null}
                {capabilities?.fast_charging ? (
                  <MetricRow
                    label="Fast charging"
                    value={
                      latest?.fast_charging === null ||
                      latest?.fast_charging === undefined
                        ? NOT_REPORTED
                        : latest.fast_charging
                          ? 'Enabled'
                          : 'Standard'
                    }
                  />
                ) : null}
                {capabilities?.indoor_temperature ? (
                  <MetricRow
                    label="Indoor temperature"
                    value={formatMetric(latest?.indoor_temperature_c, '°C', 1)}
                  />
                ) : null}
                {capabilities?.load ? (
                  <MetricRow
                    label="Current load"
                    value={formatPercent(latest?.load_percent, 1)}
                    hint="of nameplate"
                  />
                ) : null}

                <MetricRow
                  label="Last seen"
                  value={data.last_seen_at ? formatRelative(data.last_seen_at) : 'Never'}
                />
                <MetricRow
                  label="Serial"
                  value={data.serial_number ?? '—'}
                />
              </div>
            </Card>

            <Card elevation="flat" className="p-6">
              <h3 className="font-display text-sm font-semibold text-foreground">
                Recent detections
              </h3>
              {anomalies.isLoading ? (
                <Skeleton className="mt-3 h-40" />
              ) : (anomalies.data ?? []).length === 0 ? (
                <p className="mt-3 text-sm text-subtle">
                  No anomalies detected on this asset.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {(anomalies.data ?? []).map((item) => (
                    <li
                      key={item.id}
                      className="rounded-[10px] border border-border px-3 py-2.5"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <Badge tone={SEVERITY_TONE[item.severity]} size="sm">
                          {humanise(item.fault_type)}
                        </Badge>
                        <span className="text-[11px] text-subtle">
                          {formatRelative(item.detected_at)}
                        </span>
                      </div>
                      <p className="mt-1.5 text-xs leading-relaxed text-muted">
                        {item.description}
                      </p>
                      <p className="mt-1 text-[10px] text-subtle">
                        Confidence {formatPercent(item.confidence * 100, 0)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default AssetDetailPage

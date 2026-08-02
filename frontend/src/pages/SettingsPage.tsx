import {
  Activity,
  Cpu,
  Languages,
  Loader2,
  Monitor,
  Moon,
  Play,
  RotateCcw,
  Save,
  Settings as SettingsIcon,
  Square,
  Sun,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { ErrorState } from '@/components/common/ErrorState'
import { MetricRow } from '@/components/common/Metric'
import { PageSections, Section } from '@/components/common/Section'
import { LiveDot } from '@/components/common/StatusPill'
import { PageHeader, PageTransition } from '@/components/layout'
import { Badge, Button, Card, Input, Skeleton, Switch } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { useTheme } from '@/hooks/useAppContext'
import {
  usePlatformHealth,
  useSaveSettings,
  useSettings,
  useTwinControl,
  useTwinStatus,
} from '@/hooks/usePlatform'
import type { ThemePreference } from '@/context/ThemeContext'
import type { PlatformSettings } from '@/types'
import { cn } from '@/utils/cn'
import { formatNumber, humanise } from '@/utils/format'

/**
 * Settings.
 *
 * Platform preferences plus the Digital Twin control surface. The twin has
 * start, stop and reset endpoints that something has to drive, and an
 * engineering diagnostics panel is the right home for them — it keeps the
 * operational dashboards free of controls that only matter during development
 * and demonstration.
 *
 * Language is present because the SSOT specifies it, and the copy underneath
 * says plainly what it currently does. A control that silently does nothing is
 * worse than one that explains itself.
 */

function SettingsRow({
  label,
  description,
  children,
}: {
  label: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 py-4">
      <div className="min-w-0 max-w-md">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description ? (
          <p className="mt-0.5 text-xs leading-relaxed text-muted">{description}</p>
        ) : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

export function SettingsPage() {
  const settings = useSettings()
  const save = useSaveSettings()
  const health = usePlatformHealth()
  const twin = useTwinStatus()
  const control = useTwinControl()
  const { preference, setPreference } = useTheme()

  const [draft, setDraft] = useState<PlatformSettings | null>(null)

  // Seed the form once the server responds; afterwards the draft is the source
  // of truth so typing is never overwritten by a background refetch.
  useEffect(() => {
    if (settings.data && !draft) setDraft(settings.data)
  }, [settings.data, draft])

  if (settings.isError) {
    return (
      <PageTransition>
        <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />
      </PageTransition>
    )
  }

  const dirty =
    draft && settings.data ? JSON.stringify(draft) !== JSON.stringify(settings.data) : false

  const update = <K extends keyof PlatformSettings>(key: K, value: PlatformSettings[K]) => {
    setDraft((current) => (current ? { ...current, [key]: value } : current))
  }

  const themeOptions: Array<{ value: ThemePreference; label: string; icon: typeof Sun }> = [
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'system', label: 'System', icon: Monitor },
  ]

  return (
    <PageTransition>
      <PageSections>
        <PageHeader
          title={STRINGS.settings.title}
          description={STRINGS.settings.subtitle}
          icon={SettingsIcon}
          actions={
            <Button
              variant="primary"
              size="sm"
              disabled={!dirty || save.isPending}
              onClick={() => draft && save.mutate(draft)}
            >
              {save.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Save className="size-4" />
              )}
              {save.isSuccess && !dirty ? STRINGS.common.saved : STRINGS.common.save}
            </Button>
          }
        />

        {/* Appearance */}
        <Section title="Appearance" stagger={false}>
          <Card elevation="flat" className="divide-y divide-border px-6">
            <SettingsRow
              label="Theme"
              description="Dark is the platform default. Both themes are first-class and switch instantly."
            >
              <div className="flex gap-1.5">
                {themeOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      setPreference(option.value)
                      update('theme', option.value)
                    }}
                    className={cn(
                      'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
                      preference === option.value
                        ? 'border-primary/30 bg-primary-soft text-primary'
                        : 'border-border text-muted hover:border-border-strong hover:text-foreground',
                    )}
                  >
                    <option.icon className="size-3.5" />
                    {option.label}
                  </button>
                ))}
              </div>
            </SettingsRow>

            <SettingsRow
              label="Reduced motion"
              description="Also honoured automatically when your operating system requests it."
            >
              <Switch
                checked={draft?.reduced_motion ?? false}
                onCheckedChange={(checked) => update('reduced_motion', checked)}
              />
            </SettingsRow>

            <SettingsRow
              label="Language"
              description="English only at present. Interface copy is externalised so additional languages can be added without touching components."
            >
              <div className="flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-xs text-muted">
                <Languages className="size-3.5" />
                English
              </div>
            </SettingsRow>
          </Card>
        </Section>

        {/* Organisation */}
        <Section title="Organisation" stagger={false}>
          <Card elevation="flat" className="divide-y divide-border px-6">
            <SettingsRow
              label="Organisation name"
              description="Shown in the navigation bar and on the Cockpit banner."
            >
              <Input
                value={draft?.organization_name ?? ''}
                onChange={(event) => update('organization_name', event.target.value)}
                className="w-64"
                aria-label="Organisation name"
              />
            </SettingsRow>

            <SettingsRow
              label="Energy tariff"
              description="Blended rate per kWh, used to convert consumption into cost."
            >
              <Input
                type="number"
                step="0.001"
                min="0"
                value={draft?.energy_tariff_per_kwh ?? 0}
                onChange={(event) =>
                  update('energy_tariff_per_kwh', Number(event.target.value))
                }
                className="w-32"
                aria-label="Energy tariff per kilowatt hour"
              />
            </SettingsRow>

            <SettingsRow label="Currency" description="ISO code used for every monetary figure.">
              <Input
                value={draft?.currency_code ?? 'USD'}
                onChange={(event) => update('currency_code', event.target.value.toUpperCase())}
                className="w-24"
                maxLength={4}
                aria-label="Currency code"
              />
            </SettingsRow>
          </Card>
        </Section>

        {/* Notifications */}
        <Section title="Notifications" stagger={false}>
          <Card elevation="flat" className="divide-y divide-border px-6">
            <SettingsRow label="Enable notifications">
              <Switch
                checked={draft?.notifications_enabled ?? true}
                onCheckedChange={(checked) => update('notifications_enabled', checked)}
              />
            </SettingsRow>
            <SettingsRow label="Notify on critical alerts">
              <Switch
                checked={draft?.notify_on_critical ?? true}
                disabled={!draft?.notifications_enabled}
                onCheckedChange={(checked) => update('notify_on_critical', checked)}
              />
            </SettingsRow>
            <SettingsRow label="Notify on warnings">
              <Switch
                checked={draft?.notify_on_warning ?? true}
                disabled={!draft?.notifications_enabled}
                onCheckedChange={(checked) => update('notify_on_warning', checked)}
              />
            </SettingsRow>
          </Card>
        </Section>

        {/* Digital Twin */}
        <Section
          title="Digital Twin Engine"
          description="The virtual fleet generating telemetry until real sensors are connected"
          stagger={false}
        >
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            <Card elevation="secondary" className="space-y-5 p-6">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2.5">
                  <span className="grid size-9 place-items-center rounded-[10px] border border-border bg-surface-sunken text-primary">
                    <Cpu className="size-4" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Engine</p>
                    <LiveDot
                      active={twin.data?.running ?? false}
                      label={twin.data?.running ? 'Running' : 'Stopped'}
                    />
                  </div>
                </div>
                {twin.data ? (
                  <Badge tone={twin.data.running ? 'healthy' : 'neutral'} size="sm">
                    {twin.data.devices} devices
                  </Badge>
                ) : null}
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  disabled={twin.data?.running || control.start.isPending}
                  onClick={() => control.start.mutate()}
                >
                  <Play className="size-4" />
                  Start
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!twin.data?.running || control.stop.isPending}
                  onClick={() => control.stop.mutate()}
                >
                  <Square className="size-4" />
                  Pause
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={control.reset.isPending}
                  onClick={() => control.reset.mutate()}
                >
                  {control.reset.isPending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <RotateCcw className="size-4" />
                  )}
                  Reset fleet
                </Button>
              </div>

              {twin.data ? (
                <div className="divide-y divide-border border-t border-border pt-2">
                  <MetricRow
                    label="Interval"
                    value={`${twin.data.interval_seconds.toFixed(1)} s`}
                  />
                  <MetricRow label="Ticks" value={formatNumber(twin.data.ticks)} />
                  <MetricRow
                    label="Samples emitted"
                    value={formatNumber(twin.data.samples_emitted)}
                  />
                  <MetricRow
                    label="Devices unreachable"
                    value={String(twin.data.devices_offline)}
                    tone={twin.data.devices_offline > 0 ? 'warning' : undefined}
                  />
                  <MetricRow
                    label="Last tick duration"
                    value={`${twin.data.last_tick_duration_ms.toFixed(1)} ms`}
                  />
                  {twin.data.overruns > 0 ? (
                    <MetricRow
                      label="Overruns"
                      value={String(twin.data.overruns)}
                      tone="warning"
                      hint="ticks that exceeded their slot"
                    />
                  ) : null}
                </div>
              ) : (
                <Skeleton className="h-40" />
              )}
            </Card>

            <Card elevation="flat" className="space-y-5 p-6">
              <div className="flex items-center gap-2.5">
                <span className="grid size-9 place-items-center rounded-[10px] border border-border bg-surface-sunken text-primary">
                  <Activity className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-foreground">Platform health</p>
                  <p className="text-xs text-subtle">Live service diagnostics</p>
                </div>
              </div>

              {health.data ? (
                <div className="divide-y divide-border">
                  <MetricRow
                    label="Service"
                    value={health.data.status}
                    tone={health.data.status === 'ok' ? 'healthy' : 'critical'}
                  />
                  <MetricRow
                    label="Database"
                    value={health.data.database_connected ? 'Connected' : 'Unreachable'}
                    tone={health.data.database_connected ? 'healthy' : 'critical'}
                  />
                  <MetricRow label="Environment" value={humanise(health.data.environment)} />
                  <MetricRow label="Version" value={health.data.version} />
                  {twin.data?.telemetry ? (
                    <>
                      <MetricRow
                        label="Readings stored"
                        value={formatNumber(twin.data.telemetry.stored)}
                      />
                      <MetricRow
                        label="Readings rejected"
                        value={formatNumber(twin.data.telemetry.rejected)}
                        tone={twin.data.telemetry.rejected > 0 ? 'warning' : undefined}
                        hint="failed physical validation"
                      />
                    </>
                  ) : null}
                </div>
              ) : (
                <Skeleton className="h-40" />
              )}

              <p className="border-t border-border pt-4 text-xs leading-relaxed text-subtle">
                Asset and user management are part of a later phase. This panel covers the
                data source; the asset registry itself is read-only in the current release.
              </p>
            </Card>
          </div>
        </Section>
      </PageSections>
    </PageTransition>
  )
}

export default SettingsPage

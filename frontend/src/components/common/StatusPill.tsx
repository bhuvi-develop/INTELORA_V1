import { Activity, CircleDot, Wifi, WifiOff, Wrench, type LucideIcon } from 'lucide-react'

import { Badge } from '@/components/ui'
import type { ConnectivityState, HealthState, OperationalState } from '@/types'
import { cn } from '@/utils/cn'
import {
  CONNECTIVITY_LABEL,
  CONNECTIVITY_TONE,
  HEALTH_LABEL,
  HEALTH_TONE,
  OPERATIONAL_LABEL,
  toneStyle,
} from '@/utils/status'

/**
 * Status indicators for the three-dimension model.
 *
 * Health, operation and connectivity are rendered as three separate elements
 * because they are three separate facts. An asset that is *running* and
 * *warning* and *online* is a completely ordinary state, and a single combined
 * badge could only show one of those.
 *
 * Only health carries a semantic colour. Operation is neutral — an idle asset
 * is not a problem, and colouring it amber would teach users to ignore amber.
 */

export function HealthPill({
  state,
  score,
  className,
}: {
  state: HealthState
  score?: number
  className?: string
}) {
  const tone = HEALTH_TONE[state]

  return (
    <Badge tone={tone} className={className}>
      {/* Resolved through the tone map rather than interpolated: Tailwind
          extracts class names statically and a template literal would produce
          no CSS at all. */}
      <span className={cn('size-1.5 rounded-full', toneStyle(tone).solid)} />
      {HEALTH_LABEL[state]}
      {score !== undefined ? (
        <span className="tabular opacity-70">{score.toFixed(0)}</span>
      ) : null}
    </Badge>
  )
}

const OPERATIONAL_ICON: Record<OperationalState, LucideIcon> = {
  running: Activity,
  idle: CircleDot,
  maintenance: Wrench,
}

export function OperationalPill({
  state,
  className,
}: {
  state: OperationalState
  className?: string
}) {
  const Icon = OPERATIONAL_ICON[state]

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs font-medium text-muted',
        className,
      )}
    >
      <Icon
        className={cn(
          'size-3.5',
          // Movement is the signal for "running", not colour.
          state === 'running' && 'text-healthy',
        )}
      />
      {OPERATIONAL_LABEL[state]}
    </span>
  )
}

export function ConnectivityPill({
  state,
  className,
}: {
  state: ConnectivityState
  className?: string
}) {
  const Icon = state === 'offline' ? WifiOff : Wifi

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs font-medium',
        state === 'offline' ? 'text-critical' : 'text-muted',
        className,
      )}
      title={`Connectivity: ${CONNECTIVITY_LABEL[state]}`}
    >
      <Icon
        className={cn(
          'size-3.5',
          state === 'online' && toneStyle(CONNECTIVITY_TONE[state]).text,
        )}
      />
      {CONNECTIVITY_LABEL[state]}
    </span>
  )
}

/**
 * The full triple, for asset cards and detail headers.
 *
 * Presenting all three together is the clearest expression of the model, and
 * it makes the independence of the dimensions self-evident to the user.
 */
export function StatusTriple({
  health,
  healthScore,
  operational,
  connectivity,
  className,
}: {
  health: HealthState
  healthScore?: number
  operational: OperationalState
  connectivity: ConnectivityState
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-center gap-x-4 gap-y-2', className)}>
      <HealthPill state={health} score={healthScore} />
      <OperationalPill state={operational} />
      <ConnectivityPill state={connectivity} />
    </div>
  )
}

/**
 * Live indicator.
 *
 * A pulsing dot with an expanding ring. Used sparingly — on the hero banner
 * and asset cards — because an interface full of pulsing dots stops signalling
 * anything.
 */
export function LiveDot({
  active = true,
  label,
  className,
}: {
  active?: boolean
  label?: string
  className?: string
}) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span className="relative grid size-2 place-items-center">
        <span
          className={cn(
            'absolute inline-flex size-2 rounded-full',
            active ? 'bg-healthy' : 'bg-neutral',
          )}
        />
        {active ? (
          <span className="absolute inline-flex size-2 animate-[pulse-ring_2.4s_ease-out_infinite] rounded-full bg-healthy" />
        ) : null}
      </span>
      {label ? (
        <span
          className={cn(
            'text-[11px] font-semibold tracking-wider uppercase',
            active ? 'text-healthy' : 'text-subtle',
          )}
        >
          {label}
        </span>
      ) : null}
    </span>
  )
}

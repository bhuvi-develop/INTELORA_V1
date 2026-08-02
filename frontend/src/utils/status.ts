/**
 * Status presentation.
 *
 * The three status dimensions map to visual treatment here and nowhere else,
 * so health, operation and connectivity look the same on every screen. Health
 * carries the semantic colour; operation and connectivity use neutral markers,
 * because an idle asset is not a warning and colouring it as one would train
 * users to ignore real warnings.
 */

import type {
  AlertSeverity,
  AlertStatus,
  ConnectivityState,
  HealthState,
  LifecycleStage,
  OperationalState,
  RiskLevel,
  Tone,
} from '@/types'

interface ToneStyle {
  /** Text colour class. */
  text: string
  /** Soft background for pills and badges. */
  bg: string
  /** Border colour for outlined treatments. */
  border: string
  /** Solid fill, for dots and indicators. */
  solid: string
  /** CSS custom property, for passing colours into ECharts. */
  cssVar: string
}

export const TONE_STYLES: Record<Tone, ToneStyle> = {
  primary: {
    text: 'text-primary',
    bg: 'bg-primary-soft',
    border: 'border-primary/30',
    solid: 'bg-primary',
    cssVar: '--intelora-primary',
  },
  healthy: {
    text: 'text-healthy',
    bg: 'bg-healthy-soft',
    border: 'border-healthy/30',
    solid: 'bg-healthy',
    cssVar: '--intelora-healthy',
  },
  warning: {
    text: 'text-warning',
    bg: 'bg-warning-soft',
    border: 'border-warning/30',
    solid: 'bg-warning',
    cssVar: '--intelora-warning',
  },
  critical: {
    text: 'text-critical',
    bg: 'bg-critical-soft',
    border: 'border-critical/30',
    solid: 'bg-critical',
    cssVar: '--intelora-critical',
  },
  neutral: {
    text: 'text-muted',
    bg: 'bg-neutral-soft',
    border: 'border-border',
    solid: 'bg-neutral',
    cssVar: '--intelora-neutral',
  },
}

export function toneStyle(tone: Tone | string): ToneStyle {
  return TONE_STYLES[(tone as Tone) in TONE_STYLES ? (tone as Tone) : 'neutral']
}

/** Health is the only dimension that carries a semantic colour. */
export const HEALTH_TONE: Record<HealthState, Tone> = {
  healthy: 'healthy',
  warning: 'warning',
  critical: 'critical',
}

export const HEALTH_LABEL: Record<HealthState, string> = {
  healthy: 'Healthy',
  warning: 'Warning',
  critical: 'Critical',
}

export const OPERATIONAL_LABEL: Record<OperationalState, string> = {
  running: 'Running',
  idle: 'Idle',
  maintenance: 'Maintenance',
}

export const CONNECTIVITY_LABEL: Record<ConnectivityState, string> = {
  online: 'Online',
  offline: 'Offline',
  unknown: 'Unknown',
}

/**
 * Connectivity gets a muted treatment except when confirmed offline, which is
 * genuinely actionable — an asset the platform cannot reach is not being
 * monitored at all.
 */
export const CONNECTIVITY_TONE: Record<ConnectivityState, Tone> = {
  online: 'healthy',
  offline: 'critical',
  unknown: 'neutral',
}

export const SEVERITY_TONE: Record<AlertSeverity, Tone> = {
  critical: 'critical',
  warning: 'warning',
  information: 'primary',
}

export const SEVERITY_LABEL: Record<AlertSeverity, string> = {
  critical: 'Critical',
  warning: 'Warning',
  information: 'Information',
}

export const ALERT_STATUS_LABEL: Record<AlertStatus, string> = {
  active: 'Active',
  acknowledged: 'Acknowledged',
  resolved: 'Resolved',
}

/**
 * One ranking scale across every layer, so a user learns the colour language
 * once instead of relearning it per module.
 */
export const RISK_TONE: Record<RiskLevel, Tone> = {
  low: 'healthy',
  moderate: 'primary',
  high: 'warning',
  severe: 'critical',
}

export const RISK_LABEL: Record<RiskLevel, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
}

export const LIFECYCLE_LABEL: Record<LifecycleStage, string> = {
  commissioning: 'Commissioning',
  normal: 'Normal service',
  wear: 'Wear',
  end_of_life: 'End of life',
}

export const LIFECYCLE_TONE: Record<LifecycleStage, Tone> = {
  commissioning: 'primary',
  normal: 'healthy',
  wear: 'warning',
  end_of_life: 'critical',
}

/**
 * Health score to state.
 *
 * Mirrors the thresholds in `backend/app/digital_twin/device.py`. Duplicated
 * deliberately so the UI can classify a bare score client-side; the server
 * remains authoritative and sends the state alongside every reading.
 */
export function healthStateFor(score: number): HealthState {
  if (score < 52) return 'critical'
  if (score < 78) return 'warning'
  return 'healthy'
}

/** Resolve a CSS custom property to its computed colour, for ECharts. */
export function cssColor(variable: string, fallback = '#64748b'): string {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(variable)
  return value.trim() || fallback
}

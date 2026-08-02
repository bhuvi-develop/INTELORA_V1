/**
 * Chart theming.
 *
 * Charts read their colours from the same CSS custom properties as everything
 * else, resolved at render time. Hardcoding hex values here would be the
 * easiest way to break the light theme, since the primary accent differs
 * between the two.
 */

import type { EChartsOption } from 'echarts'

import type { ResolvedTheme } from '@/context/ThemeContext'
import { cssColor } from '@/utils/status'

export interface ChartTheme {
  mode: ResolvedTheme
  foreground: string
  muted: string
  subtle: string
  grid: string
  surface: string
  border: string
  primary: string
  healthy: string
  warning: string
  critical: string
  neutral: string
  /** Categorical sequence for multi-series charts. */
  palette: string[]
  fontFamily: string
}

/** Resolve the active theme from the document. */
export function resolveChartTheme(mode: ResolvedTheme): ChartTheme {
  return {
    mode,
    foreground: cssColor('--intelora-foreground', '#0f172a'),
    muted: cssColor('--intelora-foreground-muted', '#475569'),
    subtle: cssColor('--intelora-foreground-subtle', '#64748b'),
    grid: cssColor('--intelora-grid-line', 'rgba(100,116,139,0.12)'),
    surface: cssColor('--intelora-surface-raised', '#ffffff'),
    border: cssColor('--intelora-border', 'rgba(100,116,139,0.2)'),
    primary: cssColor('--intelora-primary', '#2563eb'),
    healthy: cssColor('--intelora-healthy', '#16a34a'),
    warning: cssColor('--intelora-warning', '#d97706'),
    critical: cssColor('--intelora-critical', '#dc2626'),
    neutral: cssColor('--intelora-neutral', '#64748b'),
    palette: [
      cssColor('--intelora-chart-1', '#2563eb'),
      cssColor('--intelora-chart-2', '#0d9488'),
      cssColor('--intelora-chart-3', '#d97706'),
      cssColor('--intelora-chart-4', '#7c3aed'),
      cssColor('--intelora-chart-5', '#db2777'),
      cssColor('--intelora-chart-6', '#0891b2'),
    ],
    fontFamily: "'Inter', ui-sans-serif, system-ui, sans-serif",
  }
}

/** Map a semantic tone to its resolved colour. */
export function toneColor(theme: ChartTheme, tone: string): string {
  switch (tone) {
    case 'healthy':
      return theme.healthy
    case 'warning':
      return theme.warning
    case 'critical':
      return theme.critical
    case 'primary':
      return theme.primary
    default:
      return theme.neutral
  }
}

/**
 * Options every chart inherits.
 *
 * Tooltips are styled to match the surface tokens so they read as part of the
 * interface rather than as a browser default dropped on top of it.
 */
export function baseOption(theme: ChartTheme): EChartsOption {
  return {
    /* ECharts' own accessibility layer, generating a description of the data
       for assistive technology. */
    aria: { enabled: true, decal: { show: false } },

    animation: true,
    animationDuration: 620,
    animationEasing: 'cubicOut',
    // Updates ease rather than snap, which is what makes a 1 Hz chart feel
    // continuous instead of twitchy.
    animationDurationUpdate: 420,
    animationEasingUpdate: 'cubicInOut',

    textStyle: {
      fontFamily: theme.fontFamily,
      color: theme.muted,
    },

    color: theme.palette,

    tooltip: {
      backgroundColor: theme.surface,
      borderColor: theme.border,
      borderWidth: 1,
      padding: [10, 14],
      extraCssText:
        'border-radius:12px;box-shadow:0 12px 32px -8px rgba(0,0,0,0.35);backdrop-filter:blur(8px);',
      textStyle: { color: theme.foreground, fontSize: 12 },
      axisPointer: {
        lineStyle: { color: theme.border },
        crossStyle: { color: theme.border },
      },
    },

    grid: {
      left: 8,
      right: 16,
      top: 24,
      bottom: 8,
      containLabel: true,
    },
  }
}

/** Shared axis styling, so every chart's gridlines match. */
export function axisStyle(theme: ChartTheme) {
  return {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: theme.subtle,
      fontSize: 11,
      // Tabular figures keep axis labels from shifting as values change.
      fontFamily: theme.fontFamily,
    },
    splitLine: {
      lineStyle: { color: theme.grid, type: 'dashed' as const },
    },
  }
}

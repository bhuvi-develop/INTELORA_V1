/**
 * Chart option builders.
 *
 * One function per chart form, each taking the resolved theme and returning a
 * complete ECharts option. Building them here rather than inline in pages
 * means every line chart on the platform shares axis styling, tooltip
 * behaviour and animation timing — which is what makes the analytics feel like
 * one product instead of a dozen separately-styled widgets.
 */

import type { EChartsOption } from 'echarts'

import type { ChartSeries, DistributionSlice, SeriesPoint } from '@/types'
import { axisStyle, baseOption, toneColor, type ChartTheme } from './theme'

/** Convert API points to ECharts pairs, preserving gaps as nulls. */
function toPairs(points: SeriesPoint[]): Array<[number, number | null]> {
  return points.map((point) => [
    new Date(point.t).getTime(),
    point.v ?? null,
  ])
}

/**
 * Area/line trend.
 *
 * Gaps are rendered as gaps rather than interpolated across. A straight line
 * drawn through a period when an asset was offline would assert data the
 * platform never received.
 */
export function lineOption(
  theme: ChartTheme,
  series: ChartSeries[],
  options: { area?: boolean; smooth?: boolean; showLegend?: boolean } = {},
): EChartsOption {
  const { area = true, smooth = true, showLegend = false } = options

  return {
    ...baseOption(theme),
    legend: showLegend
      ? {
          show: true,
          top: 0,
          right: 0,
          icon: 'roundRect',
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { color: theme.subtle, fontSize: 11 },
        }
      : { show: false },
    grid: { left: 8, right: 16, top: showLegend ? 34 : 16, bottom: 4, containLabel: true },
    tooltip: {
      ...baseOption(theme).tooltip,
      trigger: 'axis',
      valueFormatter: (value) =>
        value === null || value === undefined
          ? '—'
          : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}${
              series[0]?.unit ? ` ${series[0].unit}` : ''
            }`,
    },
    xAxis: {
      type: 'time',
      ...axisStyle(theme),
      splitLine: { show: false },
      axisLabel: {
        ...axisStyle(theme).axisLabel,
        hideOverlap: true,
      },
    },
    yAxis: {
      type: 'value',
      ...axisStyle(theme),
      scale: true,
    },
    series: series.map((entry, index) => {
      const color = theme.palette[index % theme.palette.length]
      return {
        name: entry.label,
        type: 'line' as const,
        smooth,
        symbol: 'none',
        connectNulls: false,
        sampling: 'lttb' as const,
        lineStyle: { width: 2, color },
        itemStyle: { color },
        ...(area
          ? {
              areaStyle: {
                opacity: 0.16,
                color: {
                  type: 'linear' as const,
                  x: 0,
                  y: 0,
                  x2: 0,
                  y2: 1,
                  colorStops: [
                    { offset: 0, color },
                    { offset: 1, color: 'transparent' },
                  ],
                },
              },
            }
          : {}),
        data: toPairs(entry.points),
      }
    }),
  }
}

/**
 * Radial gauge.
 *
 * Used for OEE and fleet health. The track is always drawn, so an empty gauge
 * still reads as a deliberate instrument rather than a broken chart.
 */
export function gaugeOption(
  theme: ChartTheme,
  value: number | null,
  options: { label?: string; max?: number; tone?: string; unit?: string } = {},
): EChartsOption {
  const { label = '', max = 100, tone = 'primary', unit = '%' } = options
  const color = toneColor(theme, tone)
  const resolved = value ?? 0

  return {
    ...baseOption(theme),
    tooltip: { show: false },
    series: [
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max,
        radius: '96%',
        center: ['50%', '58%'],
        progress: {
          show: true,
          width: 14,
          roundCap: true,
          itemStyle: { color },
        },
        axisLine: {
          lineStyle: {
            width: 14,
            color: [[1, theme.grid]],
          },
        },
        pointer: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        anchor: { show: false },
        title: {
          show: Boolean(label),
          offsetCenter: [0, '34%'],
          color: theme.subtle,
          fontSize: 11,
          fontFamily: theme.fontFamily,
        },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '2%'],
          formatter: value === null ? '—' : `{v|${resolved.toFixed(1)}}{u|${unit}}`,
          rich: {
            v: {
              fontSize: 30,
              fontWeight: 700,
              color: theme.foreground,
              fontFamily: "'Sora', sans-serif",
            },
            u: {
              fontSize: 13,
              color: theme.subtle,
              padding: [0, 0, 0, 3],
            },
          },
        },
        data: [{ value: resolved, name: label }],
      },
    ],
  }
}

/** Donut distribution. Tones come from the slice, not the palette order. */
export function donutOption(
  theme: ChartTheme,
  slices: DistributionSlice[],
  options: { centerLabel?: string; centerValue?: string } = {},
): EChartsOption {
  const total = slices.reduce((sum, slice) => sum + slice.value, 0)

  return {
    ...baseOption(theme),
    tooltip: {
      ...baseOption(theme).tooltip,
      trigger: 'item',
      formatter: (params) => {
        const point = params as { name: string; value: number; percent?: number }
        return `${point.name}<br/><strong>${point.value}</strong> (${point.percent?.toFixed(0) ?? 0}%)`
      },
    },
    legend: {
      show: true,
      bottom: 0,
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: theme.subtle, fontSize: 11 },
    },
    graphic: options.centerValue
      ? [
          {
            type: 'text',
            left: 'center',
            top: '40%',
            style: {
              text: options.centerValue,
              fill: theme.foreground,
              fontSize: 26,
              fontWeight: 700,
              fontFamily: "'Sora', sans-serif",
            },
          },
          {
            type: 'text',
            left: 'center',
            top: '54%',
            style: {
              text: options.centerLabel ?? '',
              fill: theme.subtle,
              fontSize: 11,
              fontFamily: theme.fontFamily,
            },
          },
        ]
      : undefined,
    series: [
      {
        type: 'pie',
        radius: ['62%', '84%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        padAngle: 2,
        itemStyle: { borderRadius: 6, borderWidth: 0 },
        label: { show: false },
        emphasis: {
          scaleSize: 6,
          itemStyle: { shadowBlur: 16, shadowColor: 'rgba(0,0,0,0.28)' },
        },
        data: slices.map((slice) => ({
          name: slice.label,
          value: slice.value,
          itemStyle: { color: toneColor(theme, slice.tone) },
        })),
        // An all-zero pie renders nothing at all; showing the track keeps the
        // shape of the instrument visible while awaiting data.
        ...(total === 0
          ? { data: [{ name: 'Awaiting data', value: 1, itemStyle: { color: theme.grid } }] }
          : {}),
      },
    ],
  }
}

/** Horizontal bar comparison — used for OEE by building, department and fleet. */
export function barOption(
  theme: ChartTheme,
  categories: string[],
  values: number[],
  options: { horizontal?: boolean; unit?: string; tone?: string; max?: number } = {},
): EChartsOption {
  const { horizontal = true, unit = '', tone = 'primary', max } = options
  const color = toneColor(theme, tone)

  const categoryAxis = {
    type: 'category' as const,
    data: categories,
    ...axisStyle(theme),
    splitLine: { show: false },
    axisLabel: { ...axisStyle(theme).axisLabel, width: 110, overflow: 'truncate' as const },
  }

  const valueAxis = {
    type: 'value' as const,
    ...axisStyle(theme),
    ...(max !== undefined ? { max } : {}),
    axisLabel: {
      ...axisStyle(theme).axisLabel,
      formatter: (value: number) => `${value}${unit}`,
    },
  }

  return {
    ...baseOption(theme),
    tooltip: {
      ...baseOption(theme).tooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (value) => `${Number(value).toFixed(1)}${unit}`,
    },
    grid: { left: 8, right: 24, top: 12, bottom: 8, containLabel: true },
    xAxis: horizontal ? valueAxis : categoryAxis,
    yAxis: horizontal ? { ...categoryAxis, inverse: true } : valueAxis,
    series: [
      {
        type: 'bar',
        data: values,
        barMaxWidth: 18,
        itemStyle: {
          color,
          borderRadius: horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0],
        },
      },
    ],
  }
}

/** Radar, for the APM multi-dimension profile. */
export function radarOption(
  theme: ChartTheme,
  indicators: Array<{ name: string; max: number }>,
  series: Array<{ name: string; values: number[]; tone?: string }>,
): EChartsOption {
  return {
    ...baseOption(theme),
    tooltip: { ...baseOption(theme).tooltip, trigger: 'item' },
    radar: {
      indicator: indicators,
      radius: '68%',
      center: ['50%', '54%'],
      axisName: { color: theme.subtle, fontSize: 11 },
      splitLine: { lineStyle: { color: theme.grid } },
      splitArea: { show: false },
      axisLine: { lineStyle: { color: theme.grid } },
    },
    series: [
      {
        type: 'radar',
        symbolSize: 5,
        data: series.map((entry, index) => {
          const color = entry.tone
            ? toneColor(theme, entry.tone)
            : theme.palette[index % theme.palette.length]
          return {
            name: entry.name,
            value: entry.values,
            lineStyle: { width: 2, color },
            itemStyle: { color },
            areaStyle: { opacity: 0.18, color },
          }
        }),
      },
    ],
  }
}

/**
 * Risk matrix — a quadrant scatter of likelihood against consequence.
 *
 * The quadrant bands are drawn as mark areas so the reading is immediate:
 * top-right is where attention belongs.
 */
export function riskMatrixOption(
  theme: ChartTheme,
  points: Array<{ x: number; y: number; label: string; tone: string; size: number }>,
): EChartsOption {
  return {
    ...baseOption(theme),
    tooltip: {
      ...baseOption(theme).tooltip,
      trigger: 'item',
      formatter: (params) => {
        const point = params as unknown as { value: [number, number, string, number] }
        const [x, y, label] = point.value
        return `<strong>${label}</strong><br/>Likelihood ${(x * 100).toFixed(0)}%<br/>Exposure ${y.toFixed(0)}`
      },
    },
    grid: { left: 8, right: 24, top: 20, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      name: 'Failure likelihood',
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: theme.subtle, fontSize: 11 },
      min: 0,
      max: 1,
      ...axisStyle(theme),
      axisLabel: {
        ...axisStyle(theme).axisLabel,
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    yAxis: {
      type: 'value',
      name: 'Cost exposure',
      nameTextStyle: { color: theme.subtle, fontSize: 11 },
      ...axisStyle(theme),
    },
    series: [
      {
        type: 'scatter',
        symbolSize: (data: number[]) => Math.max(8, Math.min(34, data[3] ?? 10)),
        data: points.map((point) => ({
          value: [point.x, point.y, point.label, point.size],
          itemStyle: {
            color: toneColor(theme, point.tone),
            opacity: 0.82,
            borderColor: theme.surface,
            borderWidth: 1,
          },
        })),
        markArea: {
          silent: true,
          itemStyle: { color: theme.critical, opacity: 0.05 },
          data: [[{ xAxis: 0.5, yAxis: 0 }, { xAxis: 1, yAxis: 'max' }]],
        },
      },
    ],
  }
}

/** Treemap, for APM business value by asset. */
export function treemapOption(
  theme: ChartTheme,
  nodes: Array<{ name: string; value: number; tone: string }>,
): EChartsOption {
  return {
    ...baseOption(theme),
    tooltip: {
      ...baseOption(theme).tooltip,
      formatter: (params) => {
        const node = params as { name: string; value: number }
        return `<strong>${node.name}</strong><br/>${node.value.toLocaleString()}`
      },
    },
    series: [
      {
        type: 'treemap',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        width: '100%',
        height: '100%',
        itemStyle: { borderColor: theme.surface, borderWidth: 2, gapWidth: 2 },
        label: {
          show: true,
          fontSize: 11,
          color: '#ffffff',
          overflow: 'truncate',
        },
        data: nodes.map((node) => ({
          name: node.name,
          value: node.value,
          itemStyle: { color: toneColor(theme, node.tone) },
        })),
      },
    ],
  }
}

/**
 * Alert timeline — events plotted against time and severity.
 *
 * Not one of the standard chart forms; built on scatter with a category axis
 * so each severity gets its own lane and clustering is visible at a glance.
 */
export function timelineOption(
  theme: ChartTheme,
  events: Array<{ time: string; severity: string; label: string }>,
): EChartsOption {
  const lanes = ['information', 'warning', 'critical']

  return {
    ...baseOption(theme),
    tooltip: {
      ...baseOption(theme).tooltip,
      trigger: 'item',
      formatter: (params) => {
        const point = params as unknown as { name: string; value: [number, number] }
        const date = new Date(point.value[0])
        return `<strong>${point.name}</strong><br/>${date.toLocaleString()}`
      },
    },
    grid: { left: 8, right: 20, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: 'time', ...axisStyle(theme), splitLine: { show: false } },
    yAxis: {
      type: 'category',
      data: lanes.map((lane) => lane.charAt(0).toUpperCase() + lane.slice(1)),
      ...axisStyle(theme),
      splitLine: { show: true, lineStyle: { color: theme.grid, type: 'dashed' } },
    },
    series: [
      {
        type: 'scatter',
        symbolSize: 11,
        data: events.map((event) => ({
          // The label rides on `name`: ECharts reserves `label` on a data item
          // for label *styling*, not text.
          name: event.label,
          value: [new Date(event.time).getTime(), lanes.indexOf(event.severity)],
          itemStyle: {
            color: toneColor(theme, event.severity === 'information' ? 'primary' : event.severity),
            opacity: 0.9,
          },
        })),
      },
    ],
  }
}

/** Compact sparkline for asset cards. No axes, no grid, no interaction. */
export function sparklineOption(
  theme: ChartTheme,
  values: number[],
  tone = 'primary',
): EChartsOption {
  const color = toneColor(theme, tone)

  return {
    animation: false,
    grid: { left: 0, right: 0, top: 2, bottom: 2 },
    xAxis: { type: 'category', show: false, boundaryGap: false },
    yAxis: { type: 'value', show: false, scale: true },
    tooltip: { show: false },
    series: [
      {
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.8, color },
        areaStyle: {
          opacity: 0.2,
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color },
              { offset: 1, color: 'transparent' },
            ],
          },
        },
        data: values,
      },
    ],
  }
}

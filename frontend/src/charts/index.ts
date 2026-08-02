/**
 * Chart system.
 *
 * Apache ECharts only, tree-shaken to the forms the design system specifies.
 * Every chart on the platform is built from these primitives so that axis
 * styling, tooltips, animation timing and theming stay identical across
 * modules.
 */

export { ChartCard } from './ChartCard'
export { EChart } from './EChart'
export { echarts } from './echarts'
export type { EChartsOption, EChartsType } from './echarts'
export {
  barOption,
  donutOption,
  gaugeOption,
  lineOption,
  radarOption,
  riskMatrixOption,
  sparklineOption,
  timelineOption,
  treemapOption,
} from './options'
export { axisStyle, baseOption, resolveChartTheme, toneColor } from './theme'
export type { ChartTheme } from './theme'

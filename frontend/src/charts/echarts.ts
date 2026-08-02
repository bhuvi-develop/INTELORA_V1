/**
 * ECharts module registration.
 *
 * The full ECharts bundle is roughly a megabyte. Importing it wholesale would
 * violate the platform's performance mandate outright, so this module pulls in
 * `echarts/core` and registers only the chart types and components the design
 * system actually specifies. Anything not listed here is tree-shaken away.
 *
 * Registration happens once, centrally. Scattering `use()` calls across
 * individual chart files makes the real bundle contents impossible to audit
 * and tends to drift into importing everything anyway.
 */

import {
  BarChart,
  CustomChart,
  GaugeChart,
  HeatmapChart,
  LineChart,
  PieChart,
  RadarChart,
  ScatterChart,
  SunburstChart,
  TreemapChart,
} from 'echarts/charts'
import {
  DatasetComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { LabelLayout, UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  /* Chart types — the full inventory named by the design system. Sunburst is
     registered because the specification lists it; it has no instance on any
     current screen and costs nothing until one uses it. */
  LineChart,
  BarChart,
  GaugeChart,
  PieChart,
  RadarChart,
  HeatmapChart,
  TreemapChart,
  SunburstChart,
  ScatterChart,
  CustomChart,

  /* Components */
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  VisualMapComponent,
  GraphicComponent,
  MarkLineComponent,
  MarkAreaComponent,
  MarkPointComponent,

  /* Features */
  LabelLayout,
  UniversalTransition,

  /* Canvas rather than SVG: at 1 Hz across a dozen live charts, canvas
     repaints are cheaper than mutating a large SVG DOM. */
  CanvasRenderer,
])

export { echarts }
export type { EChartsOption } from 'echarts'

/**
 * The instance type produced by the tree-shaken core build.
 *
 * Deliberately derived from `echarts.init` rather than imported from the
 * `echarts` root package: the two declare structurally different private
 * members, so the root type is not assignable to what `echarts/core` actually
 * returns.
 */
export type EChartsType = ReturnType<typeof echarts.init>

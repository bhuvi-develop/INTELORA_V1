import { useEffect, useMemo, useRef } from 'react'

import { useTheme } from '@/hooks/useAppContext'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { cn } from '@/utils/cn'
import { echarts, type EChartsOption, type EChartsType } from './echarts'
import { resolveChartTheme, type ChartTheme } from './theme'

/**
 * The ECharts React wrapper.
 *
 * This is the component every chart in the platform inherits from, and the way
 * it is built determines whether the dashboard is smooth or not.
 *
 * Three decisions matter:
 *
 * 1. **The chart instance lives outside React's render cycle**, in a ref. React
 *    owns mount, unmount and resize; ECharts owns the pixels. The instance is
 *    never recreated when data changes.
 *
 * 2. **Updates merge rather than replace.** `setOption` is called with
 *    `notMerge: false`, so ECharts diffs the new option against the current one
 *    and transitions between them. Re-initialising on every tick — the obvious
 *    implementation — would discard animation state and make a 1 Hz chart
 *    flicker.
 *
 * 3. **Resize is observed, not polled.** A `ResizeObserver` on the container
 *    handles sidebar collapse, viewport changes and panel layout shifts without
 *    a window listener that fires for unrelated reasons.
 *
 * The one case that *does* require a rebuild is a theme change, since colours
 * are baked into the option tree when it is constructed. That is handled by
 * keying the option builder on the resolved theme.
 */

interface EChartProps {
  /** Builds the option tree. Receives the resolved theme so colours stay tokenised. */
  buildOption: (theme: ChartTheme) => EChartsOption
  /** Values that should trigger an option rebuild. */
  deps?: unknown[]
  height?: number | string
  className?: string
  /** Accessible description; ECharts also generates one from the data. */
  ariaLabel?: string
  onReady?: (instance: EChartsType) => void
}

export function EChart({
  buildOption,
  deps = [],
  height = 260,
  className,
  ariaLabel,
  onReady,
}: EChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<EChartsType | null>(null)
  const { theme: mode } = useTheme()
  const reducedMotion = usePrefersReducedMotion()

  // Resolved once per theme change rather than on every render: reading
  // computed styles forces a layout pass.
  const chartTheme = useMemo(() => resolveChartTheme(mode), [mode])

  // --- Instance lifecycle ---------------------------------------------------

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const instance = echarts.init(container, undefined, {
      renderer: 'canvas',
      // Explicit sizing avoids a zero-size init when the parent is still
      // laying out, which silently produces a blank chart.
      width: container.clientWidth || undefined,
      height: container.clientHeight || undefined,
    })

    chartRef.current = instance
    onReady?.(instance)

    const observer = new ResizeObserver(() => {
      // `animation: false` on resize prevents series re-animating every time
      // the sidebar collapses.
      instance.resize({ animation: { duration: 0 } })
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      instance.dispose()
      chartRef.current = null
    }
    // Mount only. The instance must survive every data and theme change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // --- Option updates -------------------------------------------------------

  useEffect(() => {
    const instance = chartRef.current
    if (!instance) return

    const option = buildOption(chartTheme)

    instance.setOption(
      reducedMotion ? { ...option, animation: false } : option,
      {
        // Merge, so ECharts transitions between states instead of restarting.
        notMerge: false,
        // Series removed from the option must actually disappear.
        replaceMerge: ['series'],
        lazyUpdate: true,
      },
    )
    // `buildOption` is intentionally excluded — callers pass inline closures,
    // which would change identity on every render and defeat the merge.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartTheme, reducedMotion, ...deps])

  return (
    <div
      ref={containerRef}
      className={cn('w-full', className)}
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    />
  )
}

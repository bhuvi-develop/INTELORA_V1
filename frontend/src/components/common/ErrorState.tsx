import { AlertTriangle, RefreshCw, WifiOff } from 'lucide-react'
import { Component, type ErrorInfo, type ReactNode } from 'react'

import { Button, Card } from '@/components/ui'
import { STRINGS, errorMessage } from '@/constants/strings'
import { InteloraApiError } from '@/types/api'
import { cn } from '@/utils/cn'

/**
 * Error presentation.
 *
 * The API never returns stack traces, so the frontend maps error *codes* to
 * copy. A user sees what happened and what they can do; the detail stays in
 * the server log where it belongs.
 *
 * A lost connection is distinguished from a rejected request, because the two
 * call for entirely different responses from the person reading the screen.
 */

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
  className?: string
  compact?: boolean
}

export function ErrorState({ error, onRetry, className, compact }: ErrorStateProps) {
  const apiError = error instanceof InteloraApiError ? error : null
  const offline = apiError?.isOffline ?? false

  const title = offline ? STRINGS.states.offlineTitle : STRINGS.states.errorTitle
  const message = offline
    ? STRINGS.states.offlineBody
    : apiError
      ? errorMessage(apiError.code, apiError.message)
      : STRINGS.states.errorBody

  const Icon = offline ? WifiOff : AlertTriangle

  if (compact) {
    return (
      <div
        className={cn(
          'flex items-center gap-3 rounded-[12px] border border-critical/25 bg-critical-soft px-4 py-3',
          className,
        )}
        role="alert"
      >
        <Icon className="size-4 shrink-0 text-critical" />
        <p className="min-w-0 flex-1 text-sm text-foreground">{message}</p>
        {onRetry ? (
          <Button variant="ghost" size="sm" onClick={onRetry}>
            <RefreshCw className="size-3.5" />
            {STRINGS.common.retry}
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <Card
      elevation="flat"
      className={cn('flex flex-col items-center gap-4 px-6 py-12 text-center', className)}
      role="alert"
    >
      <span className="grid size-12 place-items-center rounded-full border border-critical/25 bg-critical-soft">
        <Icon className="size-5 text-critical" />
      </span>
      <div className="max-w-sm space-y-1.5">
        <h3 className="font-display text-base font-semibold text-foreground">{title}</h3>
        <p className="text-sm leading-relaxed text-muted">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="size-3.5" />
          {STRINGS.common.retry}
        </Button>
      ) : null}
    </Card>
  )
}

/**
 * Error boundary.
 *
 * Wraps the routed content so a rendering failure in one module degrades that
 * page rather than blanking the whole application — on an operations dashboard,
 * losing the navigation because a chart threw is a far worse outcome than
 * losing the chart.
 */
interface BoundaryState {
  error: Error | null
}

export class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  BoundaryState
> {
  state: BoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Left as console output deliberately: wiring this to a reporting service
    // belongs with the observability phase, and inventing an endpoint for it
    // now would be speculative.
    console.error('[INTELORA] Unhandled rendering error', error, info.componentStack)
  }

  private reset = (): void => {
    this.setState({ error: null })
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children
    if (this.props.fallback) return this.props.fallback

    return (
      <div className="p-8">
        <ErrorState error={this.state.error} onRetry={this.reset} />
      </div>
    )
  }
}

import { forwardRef, type HTMLAttributes } from 'react'

import { cn } from '@/utils/cn'

/**
 * Card.
 *
 * `elevation` encodes the design system's effect hierarchy rather than leaving
 * it to each caller's discretion. Applying the full premium treatment
 * everywhere is precisely what makes an interface look like a template, so the
 * tier is a required decision at the call site.
 *
 * - `primary` — hero verdict, KPI cards, asset cards. Lift, glow, depth.
 * - `secondary` — charts, summary tiles. Subtle lift only.
 * - `flat` — tables, forms, dense panels. No movement.
 */
type Elevation = 'primary' | 'secondary' | 'flat'

const ELEVATION: Record<Elevation, string> = {
  primary: 'glass-panel lift-primary',
  secondary: 'glass-panel lift-secondary',
  flat: 'glass-panel-flush lift-none',
}

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  elevation?: Elevation
  /** Renders the card as an interactive element with a pointer affordance. */
  interactive?: boolean
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, elevation = 'secondary', interactive = false, ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        ELEVATION[elevation],
        interactive && 'cursor-pointer',
        className,
      )}
      {...props}
    />
  )
})

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardHeader({ className, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn('flex flex-col gap-1 p-6 pb-4', className)}
        {...props}
      />
    )
  },
)

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  function CardTitle({ className, ...props }, ref) {
    return (
      <h3
        ref={ref}
        className={cn(
          'font-display text-base leading-tight font-semibold text-foreground',
          className,
        )}
        {...props}
      />
    )
  },
)

export const CardDescription = forwardRef<
  HTMLParagraphElement,
  HTMLAttributes<HTMLParagraphElement>
>(function CardDescription({ className, ...props }, ref) {
  return <p ref={ref} className={cn('text-sm text-muted', className)} {...props} />
})

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardContent({ className, ...props }, ref) {
    return <div ref={ref} className={cn('p-6 pt-0', className)} {...props} />
  },
)

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function CardFooter({ className, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn('flex items-center gap-3 border-t border-border p-6 pt-4', className)}
        {...props}
      />
    )
  },
)

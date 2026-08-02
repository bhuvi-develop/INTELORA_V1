import { cva, type VariantProps } from 'class-variance-authority'
import { forwardRef, type HTMLAttributes } from 'react'

import { cn } from '@/utils/cn'

/**
 * Badge.
 *
 * Tone maps onto the semantic tokens, so a `critical` badge is the same red on
 * every page and in both themes.
 */
const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap transition-colors',
  {
    variants: {
      tone: {
        primary: 'border-primary/25 bg-primary-soft text-primary',
        healthy: 'border-healthy/25 bg-healthy-soft text-healthy',
        warning: 'border-warning/25 bg-warning-soft text-warning',
        critical: 'border-critical/25 bg-critical-soft text-critical',
        neutral: 'border-border bg-neutral-soft text-muted',
      },
      size: {
        sm: 'px-2 py-0 text-[11px]',
        md: 'px-2.5 py-0.5 text-xs',
      },
    },
    defaultVariants: { tone: 'neutral', size: 'md' },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(function Badge(
  { className, tone, size, ...props },
  ref,
) {
  return (
    <span ref={ref} className={cn(badgeVariants({ tone, size }), className)} {...props} />
  )
})

export { badgeVariants }

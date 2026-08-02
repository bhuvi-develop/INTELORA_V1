import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { forwardRef, useCallback, useState, type ButtonHTMLAttributes } from 'react'

import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { cn } from '@/utils/cn'

/**
 * Button.
 *
 * The design system asks for gradient, glow, hover lift and ripple. Ripple is
 * not a shadcn primitive, so it is implemented here as a pooled set of
 * absolutely-positioned spans that clean themselves up on animation end —
 * cheap, and it never leaves orphaned nodes behind on a long-lived dashboard.
 *
 * All of it is suppressed under reduced motion.
 */
const buttonVariants = cva(
  [
    'relative inline-flex items-center justify-center gap-2 overflow-hidden',
    'whitespace-nowrap rounded-[12px] text-sm font-medium',
    'transition-all duration-200 ease-out',
    'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
    'disabled:pointer-events-none disabled:opacity-45',
    '[&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  ].join(' '),
  {
    variants: {
      variant: {
        /* Primary action. Gradient plus glow — used sparingly, at most once
           per view, so it retains its weight. */
        primary: [
          'bg-linear-to-br from-primary to-primary/75 text-primary-foreground font-semibold',
          'shadow-[0_4px_16px_-4px_var(--intelora-primary)]',
          'hover:-translate-y-0.5 hover:shadow-[0_8px_28px_-6px_var(--intelora-primary)]',
          'active:translate-y-0',
        ].join(' '),

        /* Default action on a glass surface. */
        secondary: [
          'bg-surface-raised text-foreground border border-border',
          'hover:border-border-strong hover:bg-surface-raised/80 hover:-translate-y-0.5',
        ].join(' '),

        outline: [
          'border border-border bg-transparent text-foreground',
          'hover:border-primary/50 hover:bg-primary-soft hover:text-primary',
        ].join(' '),

        ghost: 'bg-transparent text-muted hover:bg-primary-soft hover:text-foreground',

        danger: [
          'bg-critical text-white font-semibold',
          'hover:-translate-y-0.5 hover:shadow-[0_8px_24px_-6px_var(--intelora-critical)]',
        ].join(' '),

        /* Icon-only control in the navbar and toolbars. */
        subtle:
          'bg-transparent text-muted hover:bg-surface-raised hover:text-foreground border border-transparent hover:border-border',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        md: 'h-10 px-4',
        lg: 'h-12 px-6 text-base',
        icon: 'size-10 p-0',
        'icon-sm': 'size-8 p-0',
      },
    },
    defaultVariants: { variant: 'secondary', size: 'md' },
  },
)

interface Ripple {
  id: number
  x: number
  y: number
  size: number
}

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, asChild = false, onClick, children, ...props },
  ref,
) {
  const reducedMotion = usePrefersReducedMotion()
  const [ripples, setRipples] = useState<Ripple[]>([])

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      if (!reducedMotion && !asChild) {
        const target = event.currentTarget
        const rect = target.getBoundingClientRect()
        // Diameter large enough to cover the button from the click point,
        // whichever corner is furthest away.
        const size = Math.max(rect.width, rect.height) * 2
        setRipples((current) => [
          ...current,
          {
            id: Date.now() + Math.random(),
            x: event.clientX - rect.left - size / 2,
            y: event.clientY - rect.top - size / 2,
            size,
          },
        ])
      }
      onClick?.(event)
    },
    [onClick, reducedMotion, asChild],
  )

  const removeRipple = useCallback((id: number) => {
    setRipples((current) => current.filter((ripple) => ripple.id !== id))
  }, [])

  if (asChild) {
    return (
      <Slot
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      >
        {children}
      </Slot>
    )
  }

  return (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      onClick={handleClick}
      {...props}
    >
      {ripples.map((ripple) => (
        <span
          key={ripple.id}
          aria-hidden
          className="pointer-events-none absolute rounded-full bg-current opacity-25"
          style={{
            left: ripple.x,
            top: ripple.y,
            width: ripple.size,
            height: ripple.size,
            animation: 'ripple-expand 620ms cubic-bezier(0.16, 1, 0.3, 1) forwards',
          }}
          onAnimationEnd={() => removeRipple(ripple.id)}
        />
      ))}
      <span className="relative z-10 inline-flex items-center gap-2">{children}</span>
    </button>
  )
})

export { buttonVariants }

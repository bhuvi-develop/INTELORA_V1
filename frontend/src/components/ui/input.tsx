import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

import { cn } from '@/utils/cn'

/**
 * Input.
 *
 * Rounded, soft border, focus glow. Inputs sit in the minimal effect tier —
 * they get a focus ring and nothing else, because a text field that lifts or
 * glows while you type is a distraction rather than a delight.
 */
interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Leading adornment, typically an icon. */
  icon?: ReactNode
  /** Trailing adornment, such as a clear button or keyboard hint. */
  trailing?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, icon, trailing, ...props },
  ref,
) {
  const field = (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-[12px] border border-border bg-surface-sunken px-3 text-sm text-foreground',
        'placeholder:text-subtle',
        'transition-[border-color,box-shadow] duration-200',
        'focus:border-primary/60 focus:shadow-[0_0_0_3px_var(--intelora-primary-soft)] focus:outline-none',
        'disabled:cursor-not-allowed disabled:opacity-50',
        icon && 'pl-9',
        trailing && 'pr-10',
        className,
      )}
      {...props}
    />
  )

  if (!icon && !trailing) return field

  return (
    <div className="relative w-full">
      {icon ? (
        <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-subtle [&_svg]:size-4">
          {icon}
        </span>
      ) : null}
      {field}
      {trailing ? (
        <span className="absolute top-1/2 right-3 -translate-y-1/2 text-subtle">
          {trailing}
        </span>
      ) : null}
    </div>
  )
})

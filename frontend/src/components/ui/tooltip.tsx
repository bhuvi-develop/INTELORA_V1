import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from 'react'

import { cn } from '@/utils/cn'

/**
 * Tooltip.
 *
 * Used heavily by the collapsed sidebar, where the icon rail relies on
 * tooltips to stay usable. Radix handles the accessibility contract —
 * keyboard focus opens them, escape dismisses.
 */
export const TooltipProvider = TooltipPrimitive.Provider
export const Tooltip = TooltipPrimitive.Root
export const TooltipTrigger = TooltipPrimitive.Trigger

export const TooltipContent = forwardRef<
  ElementRef<typeof TooltipPrimitive.Content>,
  ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(function TooltipContent({ className, sideOffset = 8, ...props }, ref) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          'radix-animate z-50 max-w-64 rounded-[10px] border border-border bg-surface-raised px-3 py-2',
          'text-xs leading-relaxed text-foreground shadow-elevation-lg',
          'backdrop-blur-md',
          className,
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  )
})

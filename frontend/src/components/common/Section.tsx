import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

import { sectionReveal, staggerContainer, viewportOnce } from '@/animations/variants'
import { cn } from '@/utils/cn'

/**
 * A vertical page section.
 *
 * The layout instruction for INTELORA is emphatic: the dashboard must breathe,
 * with generous spacing and clear hierarchy, never everything crammed onto one
 * screen. This component is how that gets enforced rather than left to each
 * page's discretion — consistent vertical rhythm, a consistent heading
 * treatment, and a scroll-triggered reveal so sections arrive as the user
 * reaches them.
 *
 * The reveal fires once. Re-animating a section every time it scrolls back
 * into view is actively obstructive on a live dashboard.
 */

interface SectionProps {
  title?: string
  description?: string
  /** Rendered opposite the title: a filter, range selector or action. */
  action?: ReactNode
  /** Applies the stagger container so children reveal in sequence. */
  stagger?: boolean
  className?: string
  headerClassName?: string
  children: ReactNode
}

export function Section({
  title,
  description,
  action,
  stagger = true,
  className,
  headerClassName,
  children,
}: SectionProps) {
  return (
    <motion.section
      variants={sectionReveal}
      initial="initial"
      whileInView="animate"
      viewport={viewportOnce}
      className={cn('space-y-6', className)}
    >
      {title || action ? (
        <header
          className={cn(
            'flex flex-wrap items-end justify-between gap-4',
            headerClassName,
          )}
        >
          <div className="space-y-1">
            {title ? (
              <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
                {title}
              </h2>
            ) : null}
            {description ? (
              <p className="max-w-2xl text-sm text-muted">{description}</p>
            ) : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      ) : null}

      {stagger ? (
        <motion.div
          variants={staggerContainer}
          initial="initial"
          whileInView="animate"
          viewport={viewportOnce}
        >
          {children}
        </motion.div>
      ) : (
        children
      )}
    </motion.section>
  )
}

/**
 * Page-level vertical rhythm.
 *
 * Sections are separated by a large, consistent gap. This is the single place
 * that distance is defined, so no page can quietly become denser than the
 * others.
 */
export function PageSections({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={cn('space-y-12 lg:space-y-16', className)}>{children}</div>
}

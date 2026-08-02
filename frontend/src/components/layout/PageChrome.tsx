import { motion } from 'framer-motion'
import { ChevronRight, Home, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { pageVariants } from '@/animations/variants'
import { BRAND } from '@/constants/config'
import { NAV_LOOKUP, ROUTES } from '@/constants/navigation'
import type { Crumb } from '@/types'
import { cn } from '@/utils/cn'

/**
 * Page chrome — breadcrumb, page header, transition wrapper and footer.
 *
 * The constitution fixes the page template: navbar, sidebar, breadcrumb, page
 * title, content, footer. Keeping those pieces together means no page can
 * quietly diverge from the others.
 */

// --- Breadcrumbs ------------------------------------------------------------

/**
 * Derives the trail from the route registry, falling back to path segments for
 * detail routes the registry does not know about.
 */
export function Breadcrumbs({ trail }: { trail?: Crumb[] }) {
  const location = useLocation()

  const crumbs: Crumb[] =
    trail ??
    (() => {
      if (location.pathname === ROUTES.cockpit) return []

      const segments = location.pathname.split('/').filter(Boolean)
      const derived: Crumb[] = []
      let path = ''

      for (const segment of segments) {
        path += `/${segment}`
        const known = NAV_LOOKUP.get(path)
        derived.push({
          label:
            known?.label ??
            segment
              .split('-')
              .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
              .join(' '),
          path,
        })
      }

      return derived
    })()

  if (crumbs.length === 0) return null

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs">
      <Link
        to={ROUTES.cockpit}
        className="flex items-center gap-1.5 text-subtle transition-colors hover:text-foreground"
      >
        <Home className="size-3.5" />
        <span className="sr-only">Enterprise Cockpit</span>
      </Link>

      {crumbs.map((crumb, index) => {
        const last = index === crumbs.length - 1
        return (
          <span key={`${crumb.label}-${index}`} className="flex items-center gap-1.5">
            <ChevronRight className="size-3 text-subtle/60" />
            {last || !crumb.path ? (
              <span className="font-medium text-foreground">{crumb.label}</span>
            ) : (
              <Link
                to={crumb.path}
                className="text-subtle transition-colors hover:text-foreground"
              >
                {crumb.label}
              </Link>
            )}
          </span>
        )
      })}
    </nav>
  )
}

// --- Page header ------------------------------------------------------------

interface PageHeaderProps {
  title: string
  description?: string
  icon?: LucideIcon
  /** Layer number, shown as a marker on intelligence module pages. */
  layer?: number
  /** Compute triggers and filters live here. */
  actions?: ReactNode
  trail?: Crumb[]
}

export function PageHeader({
  title,
  description,
  icon: Icon,
  layer,
  actions,
  trail,
}: PageHeaderProps) {
  return (
    <header className="space-y-5">
      <Breadcrumbs trail={trail} />

      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="flex min-w-0 items-start gap-4">
          {Icon ? (
            <span className="grid size-12 shrink-0 place-items-center rounded-[14px] border border-border bg-surface-sunken text-primary">
              <Icon className="size-5" />
            </span>
          ) : null}

          <div className="min-w-0 space-y-1.5">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display text-2xl leading-tight font-bold tracking-tight text-foreground lg:text-3xl">
                {title}
              </h1>
              {layer ? (
                <span className="rounded-full border border-primary/25 bg-primary-soft px-2.5 py-0.5 text-[10px] font-semibold tracking-wider text-primary uppercase">
                  Layer {layer}
                </span>
              ) : null}
            </div>
            {description ? (
              <p className="max-w-3xl text-sm text-muted">{description}</p>
            ) : null}
          </div>
        </div>

        {actions ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
        ) : null}
      </div>
    </header>
  )
}

// --- Transition --------------------------------------------------------------

/**
 * Route transition.
 *
 * Fade and rise on entry. Deliberately short — a page transition that makes
 * the user wait to read data is a cost, not a flourish.
 */
export function PageTransition({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className={cn('min-h-full', className)}
    >
      {children}
    </motion.div>
  )
}

// --- Footer -------------------------------------------------------------------

export function Footer() {
  return (
    <footer className="mt-16 border-t border-border px-1 py-6">
      <div className="flex flex-col items-center justify-between gap-3 text-xs text-subtle sm:flex-row">
        <p>
          <span className="font-display font-semibold tracking-wider text-muted">
            {BRAND.name}
          </span>{' '}
          — {BRAND.tagline}
        </p>
        <p className="tabular">
          Platform v1.0.0 · Observation and advisory only
        </p>
      </div>
    </footer>
  )
}

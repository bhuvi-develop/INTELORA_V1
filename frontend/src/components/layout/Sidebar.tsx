import { AnimatePresence, motion, type Variants } from 'framer-motion'
import { ChevronsLeft, Lock } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import {
  DURATION,
  EASE_IN_OUT,
  scrimVariants,
  springSnappy,
} from '@/animations/variants'
import { LogoMark, Wordmark } from '@/components/brand/Wordmark'
import {
  Badge,
  Button,
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui'
import { LAYOUT } from '@/constants/config'
import { NAVIGATION } from '@/constants/navigation'
import { useAlertSummary } from '@/hooks/useAlerts'
import { useSidebar } from '@/hooks/useAppContext'
import type { NavItem } from '@/types'
import { cn } from '@/utils/cn'

/** The mobile sheet enters from the left, mirroring the desktop rail. */
const leftDrawerVariants: Variants = {
  initial: { x: '-100%' },
  animate: { x: 0, transition: springSnappy },
  exit: { x: '-100%', transition: { duration: DURATION.fast, ease: EASE_IN_OUT } },
}

/**
 * Primary navigation.
 *
 * Rendered from the navigation registry rather than written as markup, so a
 * new module is a config entry. Sections express the SSOT's separation of
 * Device Intelligence from Business Intelligence, and the Future Modules group
 * reserves space for roadmap items without inventing pages for them.
 *
 * Collapsed, the rail keeps only icons and relies on tooltips — which is why
 * every registry entry carries a description.
 */

function NavItemLink({
  item,
  collapsed,
  badgeCount,
  onNavigate,
}: {
  item: NavItem
  collapsed: boolean
  badgeCount?: number
  onNavigate?: () => void
}) {
  const planned = item.status === 'planned'
  const Icon = item.icon

  const content = (
    <>
      <span className="relative grid size-5 shrink-0 place-items-center">
        <Icon className="size-[18px]" />
      </span>

      {!collapsed ? (
        <>
          <span className="min-w-0 flex-1 truncate text-sm">{item.label}</span>
          {planned ? (
            <Lock className="size-3 shrink-0 text-subtle" />
          ) : badgeCount ? (
            <Badge tone="critical" size="sm" className="shrink-0 tabular">
              {badgeCount > 99 ? '99+' : badgeCount}
            </Badge>
          ) : null}
        </>
      ) : null}
    </>
  )

  const shared = cn(
    'group relative flex items-center gap-3 rounded-[12px] px-3 py-2.5',
    'font-medium transition-all duration-200',
    collapsed && 'justify-center px-0',
  )

  // Planned modules are visible but inert. Rendering them as links to routes
  // that do not exist would be worse than showing them as reserved.
  const element = planned ? (
    <div
      className={cn(shared, 'cursor-not-allowed text-subtle/70')}
      aria-disabled
      title={`${item.label} — planned`}
    >
      {content}
    </div>
  ) : (
    <NavLink
      to={item.path}
      end={item.path === '/'}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          shared,
          isActive
            ? 'bg-primary-soft text-primary'
            : 'text-muted hover:bg-surface-sunken hover:text-foreground',
        )
      }
    >
      {({ isActive }) => (
        <>
          {/* Active indicator: a rail on the leading edge, which survives
              collapse where a background tint alone would not. */}
          {isActive ? (
            <motion.span
              layoutId="sidebar-active-rail"
              className="absolute inset-y-1.5 -left-3 w-[3px] rounded-r-full bg-primary"
              transition={{ type: 'spring', stiffness: 380, damping: 32 }}
            />
          ) : null}
          {content}
        </>
      )}
    </NavLink>
  )

  if (!collapsed) return element

  return (
    <Tooltip delayDuration={120}>
      <TooltipTrigger asChild>{element}</TooltipTrigger>
      <TooltipContent side="right">
        <p className="font-medium text-foreground">{item.label}</p>
        <p className="mt-0.5 text-subtle">{item.description}</p>
        {planned ? <p className="mt-1 text-primary">Planned module</p> : null}
      </TooltipContent>
    </Tooltip>
  )
}

function SidebarBody({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean
  onNavigate?: () => void
}) {
  const { data: alerts } = useAlertSummary()

  return (
    <nav className="flex h-full flex-col gap-6 overflow-y-auto px-3 pt-2 pb-6">
      {NAVIGATION.map((section) => (
        <div key={section.key} className="space-y-1">
          {section.label && !collapsed ? (
            <p className="px-3 pb-1 text-[10px] font-semibold tracking-[0.14em] text-subtle uppercase">
              {section.label}
            </p>
          ) : null}
          {section.label && collapsed ? (
            <div className="mx-3 mb-2 h-px bg-border" aria-hidden />
          ) : null}

          <div className="space-y-0.5">
            {section.items.map((item) => (
              <NavItemLink
                key={item.key}
                item={item}
                collapsed={collapsed}
                badgeCount={item.badge === 'alerts' ? alerts?.active : undefined}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        </div>
      ))}
    </nav>
  )
}

export function Sidebar() {
  const { collapsed, toggleCollapsed, isMobile, mobileOpen, setMobileOpen } = useSidebar()
  const location = useLocation()

  // --- Mobile: an overlay sheet ---------------------------------------------

  if (isMobile) {
    return (
      <AnimatePresence>
        {mobileOpen ? (
          <>
            <motion.div
              variants={scrimVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              className="fixed inset-0 z-40 bg-[var(--intelora-scrim)] backdrop-blur-sm lg:hidden"
              onClick={() => setMobileOpen(false)}
              aria-hidden
            />
            <motion.aside
              variants={leftDrawerVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              className="fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r border-border bg-surface lg:hidden"
            >
              <div className="flex h-[72px] shrink-0 items-center gap-3 border-b border-border px-5">
                <LogoMark className="size-8" />
                <Wordmark size="text-base" />
              </div>
              <SidebarBody collapsed={false} onNavigate={() => setMobileOpen(false)} />
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>
    )
  }

  // --- Desktop: a permanent rail --------------------------------------------

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? LAYOUT.sidebarCollapsedWidth : LAYOUT.sidebarWidth }}
      transition={{ type: 'spring', stiffness: 280, damping: 32 }}
      className={cn(
        'fixed inset-y-0 left-0 z-30 hidden flex-col lg:flex',
        'border-r border-border bg-surface/80 backdrop-blur-xl',
      )}
    >
      <div
        className={cn(
          'flex h-[72px] shrink-0 items-center border-b border-border',
          collapsed ? 'justify-center px-0' : 'gap-3 px-5',
        )}
      >
        <LogoMark className="size-8 shrink-0" />
        {!collapsed ? <Wordmark size="text-base" /> : null}
      </div>

      <div className="min-h-0 flex-1">
        <SidebarBody collapsed={collapsed} />
      </div>

      <div className="shrink-0 border-t border-border p-3">
        <Button
          variant="ghost"
          size={collapsed ? 'icon-sm' : 'sm'}
          onClick={toggleCollapsed}
          className={cn('w-full', collapsed && 'mx-auto w-8')}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronsLeft
            className={cn('size-4 transition-transform duration-300', collapsed && 'rotate-180')}
          />
          {!collapsed ? <span className="text-xs">Collapse</span> : null}
        </Button>
      </div>

      {/* Screen readers announce the current location on navigation. */}
      <span className="sr-only" aria-live="polite">
        {location.pathname}
      </span>
    </motion.aside>
  )
}

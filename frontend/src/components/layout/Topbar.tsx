import {
  Bell,
  Check,
  ChevronDown,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Search,
  Settings as SettingsIcon,
  Sun,
  UserRound,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { LogoMark, Wordmark } from '@/components/brand/Wordmark'
import { LiveDot } from '@/components/common/StatusPill'
import {
  Avatar,
  AvatarFallback,
  Badge,
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Separator,
} from '@/components/ui'
import { ROUTES } from '@/constants/navigation'
import { useAlertSummary } from '@/hooks/useAlerts'
import { useLive, useSidebar, useTheme } from '@/hooks/useAppContext'
import { useClock } from '@/hooks/useClock'
import { useCockpitOverview } from '@/hooks/useDashboard'
import type { ThemePreference } from '@/context/ThemeContext'
import { cn } from '@/utils/cn'
import { formatDate, formatRelative, formatTime, initials } from '@/utils/format'
import { SEVERITY_TONE } from '@/utils/status'

/**
 * Top navigation.
 *
 * Fixed at 72px with a glass background. Carries the logo, global search,
 * organisation, live clock, connection state, theme control, notifications and
 * profile — the full set the design system specifies.
 */

// --- Connection indicator ------------------------------------------------------

/**
 * Live stream state.
 *
 * Worth surfacing prominently: on a platform whose value proposition is
 * real-time intelligence, a silently dead socket showing stale numbers is the
 * most damaging possible failure. Better to say so.
 */
function ConnectionBadge() {
  const { connection } = useLive()

  const config = {
    open: { label: 'Live', tone: 'healthy' as const, active: true },
    connecting: { label: 'Connecting', tone: 'warning' as const, active: false },
    reconnecting: { label: 'Reconnecting', tone: 'warning' as const, active: false },
    closed: { label: 'Offline', tone: 'critical' as const, active: false },
  }[connection]

  return (
    <div className="hidden items-center gap-2 rounded-full border border-border bg-surface-sunken px-3 py-1.5 md:flex">
      <LiveDot active={config.active} />
      <span
        className={cn(
          'text-[11px] font-semibold tracking-wider uppercase',
          config.tone === 'healthy' && 'text-healthy',
          config.tone === 'warning' && 'text-warning',
          config.tone === 'critical' && 'text-critical',
        )}
      >
        {config.label}
      </span>
    </div>
  )
}

// --- Clock ---------------------------------------------------------------------

function Clock() {
  const now = useClock()

  return (
    <div className="hidden flex-col items-end leading-tight xl:flex">
      <span className="tabular font-display text-sm font-semibold text-foreground">
        {formatTime(now)}
      </span>
      <span className="text-[11px] text-subtle">{formatDate(now)}</span>
    </div>
  )
}

// --- Theme -----------------------------------------------------------------------

function ThemeControl() {
  const { preference, theme, setPreference } = useTheme()

  const options: Array<{ value: ThemePreference; label: string; icon: typeof Sun }> = [
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'system', label: 'System', icon: Monitor },
  ]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="subtle" size="icon" aria-label="Change theme">
          {theme === 'dark' ? <Moon className="size-4" /> : <Sun className="size-4" />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-44">
        <DropdownMenuLabel>Appearance</DropdownMenuLabel>
        {options.map((option) => (
          <DropdownMenuItem
            key={option.value}
            onSelect={() => setPreference(option.value)}
            className={cn(preference === option.value && 'text-foreground')}
          >
            <option.icon className="size-4" />
            <span className="flex-1">{option.label}</span>
            {preference === option.value ? (
              <Check className="size-3.5 text-primary" />
            ) : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// --- Notifications ---------------------------------------------------------------

/**
 * Notification centre.
 *
 * A delivery inbox, distinct from the Alerts page. The SSOT keeps alerts and
 * notifications as separate concepts, and conflating them would mean the badge
 * counts one thing while the page lists another.
 */
function NotificationMenu() {
  const { data: alerts } = useAlertSummary()
  const navigate = useNavigate()
  const unread = alerts?.active ?? 0

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="subtle" size="icon" className="relative" aria-label="Notifications">
          <Bell className="size-4" />
          {unread > 0 ? (
            <span className="absolute top-1.5 right-1.5 grid min-w-4 place-items-center rounded-full bg-critical px-1 text-[9px] leading-4 font-bold text-white">
              {unread > 9 ? '9+' : unread}
            </span>
          ) : null}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-88 max-w-[calc(100vw-24px)] p-0">
        <div className="flex items-center justify-between px-4 py-3">
          <div>
            <p className="font-display text-sm font-semibold text-foreground">Notifications</p>
            <p className="text-xs text-subtle">
              {unread} active {unread === 1 ? 'alert' : 'alerts'}
            </p>
          </div>
          {alerts?.critical ? (
            <Badge tone="critical" size="sm">
              {alerts.critical} critical
            </Badge>
          ) : null}
        </div>

        <Separator />

        <div className="max-h-80 overflow-y-auto py-1">
          {alerts?.recent?.length ? (
            alerts.recent.slice(0, 6).map((alert) => (
              <button
                key={alert.id}
                type="button"
                onClick={() => navigate(`/alerts/${alert.id}`)}
                className="flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-sunken"
              >
                <span
                  className={cn(
                    'mt-1.5 size-2 shrink-0 rounded-full',
                    alert.severity === 'critical' && 'bg-critical',
                    alert.severity === 'warning' && 'bg-warning',
                    alert.severity === 'information' && 'bg-primary',
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-foreground">
                    {alert.title}
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-subtle">
                    {alert.asset_code} · {formatRelative(alert.triggered_at)}
                  </span>
                </span>
                <Badge tone={SEVERITY_TONE[alert.severity]} size="sm" className="shrink-0">
                  {alert.severity}
                </Badge>
              </button>
            ))
          ) : (
            <p className="px-4 py-8 text-center text-sm text-subtle">
              No notifications. The platform is quiet.
            </p>
          )}
        </div>

        <Separator />
        <div className="p-2">
          <Button variant="ghost" size="sm" className="w-full" asChild>
            <Link to={ROUTES.alerts}>View all alerts</Link>
          </Button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// --- Profile ---------------------------------------------------------------------

/**
 * Profile menu.
 *
 * Authentication is a later phase, so this shows the platform operator rather
 * than a signed-in identity. It is not a fabricated user account — the role
 * shown is the platform's own default, and sign-out is absent because there is
 * no session to end.
 */
function ProfileMenu({ organization }: { organization: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 rounded-full border border-transparent p-0.5 transition-colors hover:border-border"
          aria-label="Profile"
        >
          <Avatar className="size-8">
            <AvatarFallback>{initials(organization)}</AvatarFallback>
          </Avatar>
          <ChevronDown className="mr-1 hidden size-3.5 text-subtle lg:block" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-64">
        <div className="flex items-center gap-3 px-3 py-3">
          <Avatar className="size-10">
            <AvatarFallback>{initials(organization)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{organization}</p>
            <p className="text-xs text-subtle">Platform operator</p>
          </div>
        </div>

        <DropdownMenuSeparator />

        <DropdownMenuItem asChild>
          <Link to={ROUTES.settings}>
            <UserRound className="size-4" />
            Profile &amp; preferences
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to={ROUTES.settings}>
            <SettingsIcon className="size-4" />
            Platform settings
          </Link>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem disabled>
          <LogOut className="size-4" />
          <span className="flex-1">Sign out</span>
          <span className="text-[10px] text-subtle">Phase 2</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// --- Topbar ----------------------------------------------------------------------

export function Topbar({ onOpenSearch }: { onOpenSearch: () => void }) {
  const { isMobile, setMobileOpen } = useSidebar()
  const { data: overview } = useCockpitOverview()
  const organization = overview?.organization ?? 'INTELORA'

  return (
    <header
      className={cn(
        'sticky top-0 z-20 flex h-[72px] shrink-0 items-center gap-3 px-4 lg:px-8',
        'border-b border-border bg-background/72 backdrop-blur-xl',
      )}
    >
      {isMobile ? (
        <>
          <Button
            variant="subtle"
            size="icon"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="size-4" />
          </Button>
          <Link to={ROUTES.cockpit} className="flex items-center gap-2">
            <LogoMark className="size-7" />
            <Wordmark size="text-sm" />
          </Link>
        </>
      ) : (
        <div className="min-w-0">
          <p className="truncate font-display text-sm font-semibold text-foreground">
            {organization}
          </p>
          <p className="text-[11px] text-subtle">Enterprise AIOT Intelligence Platform</p>
        </div>
      )}

      {/* Global search. A button rather than an input: it opens the command
          palette, and presenting it as a field would imply typing happens
          in place. */}
      <button
        type="button"
        onClick={onOpenSearch}
        className={cn(
          'mx-auto hidden h-10 w-full max-w-md items-center gap-2.5 rounded-[12px] md:flex',
          'border border-border bg-surface-sunken px-3.5 text-sm text-subtle',
          'transition-colors hover:border-border-strong hover:text-muted',
        )}
      >
        <Search className="size-4" />
        <span className="flex-1 text-left">Search assets, alerts, modules…</span>
        <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-subtle">
          ⌘K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-2 md:ml-0 md:gap-3">
        <Button
          variant="subtle"
          size="icon"
          className="md:hidden"
          onClick={onOpenSearch}
          aria-label="Search"
        >
          <Search className="size-4" />
        </Button>

        <ConnectionBadge />
        <Clock />

        <Separator orientation="vertical" className="hidden h-8 lg:block" />

        <ThemeControl />
        <NotificationMenu />
        <ProfileMenu organization={organization} />
      </div>
    </header>
  )
}

import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'

import { fadeUp } from '@/animations/variants'
import { Button } from '@/components/ui'
import { STRINGS } from '@/constants/strings'
import { cn } from '@/utils/cn'

/**
 * Empty states.
 *
 * These carry real weight in INTELORA: a deployment starts with no data, a
 * filter can exclude everything, and a source can stop reporting. Each of
 * those is a different situation and deserves different copy — telling a user
 * "no results" when the backend is simply not running sends them looking in
 * the wrong place.
 *
 * The illustrations are inline SVG rather than Lucide icons. Icons are for
 * labelling; an empty state needs something with enough presence to hold a
 * section, and inline SVG keeps it theme-aware and adds no network request.
 */

type Variant = 'default' | 'awaiting' | 'noResults' | 'chart'

function AwaitingIllustration() {
  return (
    <svg viewBox="0 0 120 88" className="h-20 w-28" fill="none" aria-hidden>
      <defs>
        <linearGradient id="empty-fade" x1="0" y1="0" x2="0" y2="88">
          <stop offset="0%" stopColor="var(--intelora-primary)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--intelora-primary)" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {/* A signal that fades into nothing — the visual argument for "waiting". */}
      <path
        d="M4 62 C 20 62, 24 40, 34 40 S 48 58, 58 58 S 72 26, 84 26 S 100 46, 116 46"
        stroke="url(#empty-fade)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray="5 7"
      />
      <circle cx="34" cy="40" r="3.5" fill="var(--intelora-primary)" opacity="0.55" />
      <circle cx="84" cy="26" r="3.5" fill="var(--intelora-primary)" opacity="0.3" />
      <line
        x1="4"
        y1="76"
        x2="116"
        y2="76"
        stroke="var(--intelora-border)"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

function NoResultsIllustration() {
  return (
    <svg viewBox="0 0 120 88" className="h-20 w-28" fill="none" aria-hidden>
      <rect
        x="18"
        y="20"
        width="84"
        height="12"
        rx="4"
        fill="var(--intelora-border)"
        opacity="0.5"
      />
      <rect
        x="18"
        y="40"
        width="60"
        height="12"
        rx="4"
        fill="var(--intelora-border)"
        opacity="0.32"
      />
      <rect
        x="18"
        y="60"
        width="72"
        height="12"
        rx="4"
        fill="var(--intelora-border)"
        opacity="0.18"
      />
      <circle
        cx="86"
        cy="58"
        r="16"
        stroke="var(--intelora-primary)"
        strokeWidth="2.5"
        opacity="0.6"
      />
      <line
        x1="97"
        y1="70"
        x2="108"
        y2="81"
        stroke="var(--intelora-primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
        opacity="0.6"
      />
    </svg>
  )
}

interface EmptyStateProps {
  variant?: Variant
  title?: string
  message?: string
  /** Call to action. Omitted when there is genuinely nothing useful to do. */
  action?: { label: string; to: string }
  className?: string
}

export function EmptyState({
  variant = 'default',
  title,
  message,
  action,
  className,
}: EmptyStateProps) {
  // A chart's empty state sits inside an existing panel, so it is compact and
  // has no illustration — the panel already provides the frame.
  if (variant === 'chart') {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-2 px-6 py-8 text-center',
          className,
        )}
      >
        <span className="size-1.5 animate-pulse rounded-full bg-primary/50" />
        <p className="text-xs text-subtle">{message ?? STRINGS.states.emptyBody}</p>
      </div>
    )
  }

  const copy = {
    awaiting: {
      title: title ?? STRINGS.states.awaitingTitle,
      message: message ?? STRINGS.states.awaitingBody,
      illustration: <AwaitingIllustration />,
    },
    noResults: {
      title: title ?? STRINGS.states.noResultsTitle,
      message: message ?? STRINGS.states.noResultsBody,
      illustration: <NoResultsIllustration />,
    },
    default: {
      title: title ?? STRINGS.states.emptyTitle,
      message: message ?? STRINGS.states.emptyBody,
      illustration: <AwaitingIllustration />,
    },
  }[variant]

  return (
    <motion.div
      variants={fadeUp}
      initial="initial"
      animate="animate"
      className={cn(
        'flex flex-col items-center justify-center gap-4 px-6 py-14 text-center',
        className,
      )}
    >
      <div className="opacity-80">{copy.illustration}</div>
      <div className="max-w-sm space-y-1.5">
        <h3 className="font-display text-base font-semibold text-foreground">
          {copy.title}
        </h3>
        <p className="text-sm leading-relaxed text-muted">{copy.message}</p>
      </div>
      {action ? (
        <Button variant="outline" size="sm" asChild>
          <Link to={action.to}>{action.label}</Link>
        </Button>
      ) : null}
    </motion.div>
  )
}

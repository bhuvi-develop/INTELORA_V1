/**
 * Motion vocabulary.
 *
 * Every animation in INTELORA comes from here, so timing and easing stay
 * consistent across pages. The effect hierarchy from the design system is
 * encoded in the variant names: `primary` treatments are reserved for the hero
 * verdict, KPI cards and asset cards; `secondary` for charts and tiles;
 * `minimal` for tables and forms.
 *
 * Everything animates `transform` and `opacity` only. Animating layout
 * properties would force reflow on every frame, which at 1 Hz telemetry across
 * a dozen live charts is the difference between smooth and stuttering.
 */

import type { Transition, Variants } from 'framer-motion'

/** Apple-style deceleration: fast departure, long settle. */
export const EASE_OUT_EXPO = [0.16, 1, 0.3, 1] as const
export const EASE_IN_OUT = [0.4, 0, 0.2, 1] as const

export const DURATION = {
  instant: 0.12,
  fast: 0.22,
  base: 0.38,
  slow: 0.62,
  splash: 4.6,
} as const

export const springSoft: Transition = {
  type: 'spring',
  stiffness: 260,
  damping: 30,
  mass: 0.9,
}

export const springSnappy: Transition = {
  type: 'spring',
  stiffness: 420,
  damping: 34,
  mass: 0.7,
}

/** Page-level fade and rise, applied by the route transition wrapper. */
export const pageVariants: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.base, ease: EASE_OUT_EXPO },
  },
  exit: {
    opacity: 0,
    y: -8,
    transition: { duration: DURATION.fast, ease: EASE_IN_OUT },
  },
}

/**
 * Stagger container. Children reveal in sequence rather than together, which
 * reads as considered rather than abrupt — and gives the eye an order to
 * follow, supporting the five-second comprehension target.
 */
export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: { staggerChildren: 0.055, delayChildren: 0.04 },
  },
}

/** Primary tier: KPI cards, asset cards, the hero verdict. */
export const riseIn: Variants = {
  initial: { opacity: 0, y: 22, scale: 0.985 },
  animate: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: DURATION.base, ease: EASE_OUT_EXPO },
  },
}

/** Secondary tier: charts, summary tiles, navigation. */
export const fadeUp: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.base, ease: EASE_OUT_EXPO },
  },
}

/** Minimal tier: table rows, list items. Opacity only. */
export const fadeIn: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: DURATION.fast } },
  exit: { opacity: 0, transition: { duration: DURATION.instant } },
}

/** Sections reveal as they enter the viewport during scroll. */
export const sectionReveal: Variants = {
  initial: { opacity: 0, y: 28 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.slow, ease: EASE_OUT_EXPO },
  },
}

/** Sidebar collapse. Width is animated on a fixed-position element only. */
export const sidebarVariants: Variants = {
  expanded: { width: 280, transition: springSoft },
  collapsed: { width: 76, transition: springSoft },
}

/** Drawers and sheets. */
export const drawerVariants: Variants = {
  initial: { x: '100%' },
  animate: { x: 0, transition: springSnappy },
  exit: { x: '100%', transition: { duration: DURATION.fast, ease: EASE_IN_OUT } },
}

/** Menus and popovers. */
export const popVariants: Variants = {
  initial: { opacity: 0, scale: 0.96, y: -6 },
  animate: { opacity: 1, scale: 1, y: 0, transition: { duration: DURATION.fast, ease: EASE_OUT_EXPO } },
  exit: { opacity: 0, scale: 0.98, y: -4, transition: { duration: DURATION.instant } },
}

/** Modal scrim. */
export const scrimVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: DURATION.fast } },
  exit: { opacity: 0, transition: { duration: DURATION.fast } },
}

/**
 * The splash sequence.
 *
 * Timings are tuned to the 4–5 second brand specification and sum to roughly
 * 4.6s: particles settle, the wordmark resolves, light sweeps across it, the
 * camera pushes in, then everything clears for the dashboard already mounted
 * behind it.
 */
export const splash = {
  particles: {
    initial: { opacity: 0 },
    animate: { opacity: 1, transition: { duration: 1.1, ease: EASE_IN_OUT } },
    exit: { opacity: 0, transition: { duration: 0.5 } },
  } satisfies Variants,

  wordmark: {
    initial: { opacity: 0, scale: 0.92, filter: 'blur(14px)' },
    animate: {
      opacity: 1,
      scale: 1,
      filter: 'blur(0px)',
      transition: { duration: 1.5, delay: 0.45, ease: EASE_OUT_EXPO },
    },
    exit: {
      opacity: 0,
      scale: 1.16,
      filter: 'blur(10px)',
      transition: { duration: 0.75, ease: EASE_IN_OUT },
    },
  } satisfies Variants,

  /** Slow push-in that continues under the exit, so the cut is never static. */
  camera: {
    initial: { scale: 1.06 },
    animate: { scale: 1, transition: { duration: 4.2, ease: 'linear' } },
    exit: { scale: 1.1, transition: { duration: 0.75, ease: EASE_IN_OUT } },
  } satisfies Variants,

  /** Vertical float, deliberately tiny — it should read as buoyancy, not bounce. */
  float: {
    animate: {
      y: [0, -7, 0],
      transition: { duration: 5.4, repeat: Infinity, ease: EASE_IN_OUT },
    },
  } satisfies Variants,

  curtain: {
    initial: { opacity: 1 },
    exit: { opacity: 0, transition: { duration: 0.85, ease: EASE_IN_OUT } },
  } satisfies Variants,
} as const

/**
 * Viewport options for scroll-triggered reveals. `once` matters: re-animating
 * a section every time it scrolls back into view is distracting and, on a live
 * dashboard, actively obstructive.
 */
export const viewportOnce = { once: true, margin: '-80px' } as const

/**
 * Navigation contracts.
 *
 * The sidebar is registry-driven rather than hand-written markup. Modules on
 * the roadmap that have no screen yet are declared as `planned`, which
 * reserves their place without inventing a page: shipping one later flips a
 * flag instead of restructuring navigation.
 */

import type { LucideIcon } from 'lucide-react'

export type NavStatus = 'active' | 'planned'

export interface NavItem {
  /** Stable identifier, also used as the React key. */
  key: string
  label: string
  path: string
  icon: LucideIcon
  /** `planned` entries render disabled with a "soon" marker. */
  status: NavStatus
  /** One-line description shown in the collapsed-sidebar tooltip. */
  description: string
  /** Which intelligence layer this module surfaces, where applicable. */
  layer?: number
  /** Badge key resolved against live counts, e.g. active alerts. */
  badge?: 'alerts'
}

export interface NavSection {
  key: string
  /** Omitted for the primary section, which needs no heading. */
  label?: string
  items: NavItem[]
}

/** One crumb in the breadcrumb trail. */
export interface Crumb {
  label: string
  path?: string
}

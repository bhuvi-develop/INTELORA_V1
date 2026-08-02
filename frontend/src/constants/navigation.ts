/**
 * Navigation registry.
 *
 * The sidebar renders from this array. Modules on the roadmap that have no
 * screen yet are declared `planned`, which reserves their place in the
 * information architecture without inventing a page — shipping one later flips
 * a status rather than restructuring navigation.
 *
 * Preventive Maintenance and Prescriptive Optimisation are intentionally
 * absent as destinations: the SSOT maps them to outputs *inside* the Predictive
 * and APM screens and to the Cockpit's cost-saving KPI, not to routes.
 */

import {
  Activity,
  BatteryCharging,
  BellRing,
  Boxes,
  FileBarChart,
  Gauge,
  LayoutDashboard,
  Settings,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Zap,
} from 'lucide-react'

import type { NavSection } from '@/types'

export const ROUTES = {
  cockpit: '/',
  anomaly: '/anomaly',
  predictive: '/predictive',
  oee: '/oee',
  apm: '/apm',
  alerts: '/alerts',
  alertDetail: '/alerts/:alertId',
  reports: '/reports',
  settings: '/settings',
  assets: '/assets',
  assetDetail: '/assets/:assetId',
  energy: '/energy',
} as const

export const NAVIGATION: NavSection[] = [
  {
    key: 'command',
    items: [
      {
        key: 'cockpit',
        label: 'Enterprise Cockpit',
        path: ROUTES.cockpit,
        icon: LayoutDashboard,
        status: 'active',
        description: 'Mission control across every intelligence layer',
      },
    ],
  },
  {
    key: 'device-intelligence',
    label: 'Device Intelligence',
    items: [
      {
        key: 'anomaly',
        label: 'Anomaly Detection',
        path: ROUTES.anomaly,
        icon: ShieldAlert,
        status: 'active',
        layer: 1,
        description: 'Abnormal behaviour detected across the estate',
      },
      {
        key: 'predictive',
        label: 'Predictive Maintenance',
        path: ROUTES.predictive,
        icon: TrendingUp,
        status: 'active',
        layer: 2,
        description: 'Failure forecasts, remaining life and service windows',
      },
      {
        key: 'assets',
        label: 'Asset Registry',
        path: ROUTES.assets,
        icon: Boxes,
        status: 'active',
        description: 'Every monitored device and its live condition',
      },
    ],
  },
  {
    key: 'business-intelligence',
    label: 'Business Intelligence',
    items: [
      {
        key: 'apm',
        label: 'Asset Performance',
        path: ROUTES.apm,
        icon: Activity,
        status: 'active',
        layer: 5,
        description: 'Reliability engineering and business exposure',
      },
      {
        key: 'oee',
        label: 'Overall Equipment Efficiency',
        path: ROUTES.oee,
        icon: Gauge,
        status: 'active',
        layer: 6,
        description: 'Availability, performance and quality rollups',
      },
      {
        key: 'energy',
        label: 'Energy Analytics',
        path: ROUTES.energy,
        icon: Zap,
        status: 'active',
        description: 'Consumption, cost and metering coverage',
      },
    ],
  },
  {
    key: 'operations',
    label: 'Operations',
    items: [
      {
        key: 'alerts',
        label: 'Alerts',
        path: ROUTES.alerts,
        icon: BellRing,
        status: 'active',
        layer: 1,
        description: 'Operator queue with acknowledge and resolve',
        badge: 'alerts',
      },
      {
        key: 'reports',
        label: 'Reports',
        path: ROUTES.reports,
        icon: FileBarChart,
        status: 'active',
        description: 'Energy, health, maintenance and telemetry exports',
      },
      {
        key: 'settings',
        label: 'Settings',
        path: ROUTES.settings,
        icon: Settings,
        status: 'active',
        description: 'Theme, organisation, tariff and Digital Twin control',
      },
    ],
  },
  {
    key: 'future',
    label: 'Future Modules',
    items: [
      {
        key: 'sustainability',
        label: 'Sustainability',
        path: '/sustainability',
        icon: Sparkles,
        status: 'planned',
        description: 'Carbon accounting and reduction targets',
      },
      {
        key: 'storage',
        label: 'Energy Storage',
        path: '/storage',
        icon: BatteryCharging,
        status: 'planned',
        description: 'Battery and UPS fleet intelligence',
      },
    ],
  },
]

/** Flat lookup of active routes, used to build breadcrumbs. */
export const NAV_LOOKUP = new Map(
  NAVIGATION.flatMap((section) => section.items).map((item) => [item.path, item]),
)

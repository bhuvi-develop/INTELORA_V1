/**
 * User-facing copy.
 *
 * Externalised because the Settings page exposes a language control while the
 * sanctioned stack contains no i18n library. Retrofitting internationalisation
 * is one of the most invasive frontend refactors there is — it touches every
 * component — so strings live here from the start. Adding a library later
 * means wrapping this object, not rewriting views.
 */

export const STRINGS = {
  common: {
    loading: 'Loading',
    retry: 'Try again',
    search: 'Search',
    filter: 'Filter',
    clear: 'Clear',
    close: 'Close',
    save: 'Save changes',
    saved: 'Saved',
    cancel: 'Cancel',
    export: 'Export',
    viewAll: 'View all',
    notReported: 'Not reported',
    of: 'of',
  },

  states: {
    /** Shown when a surface has loaded successfully but holds no rows. */
    emptyTitle: 'Nothing to show yet',
    emptyBody: 'This view will populate as the platform collects data.',

    /** Shown when no data source is attached at all. */
    awaitingTitle: 'Awaiting telemetry',
    awaitingBody:
      'No source is currently reporting. Start the Digital Twin Engine or connect a sensor gateway to begin streaming.',
    awaitingAction: 'Open Settings',

    errorTitle: 'Something went wrong',
    errorBody:
      'The platform could not complete this request. The incident has been logged.',

    offlineTitle: 'Connection lost',
    offlineBody:
      'INTELORA cannot reach the intelligence services. Reconnecting automatically.',

    noResultsTitle: 'No matches',
    noResultsBody: 'No records match the current filters. Try widening your search.',
  },

  cockpit: {
    title: 'Enterprise Cockpit',
    subtitle: 'Mission control across every intelligence layer',
    welcome: 'Welcome back',
    kpiSection: 'Executive indicators',
    assetSection: 'Asset overview',
    assetSubtitle: 'Fleet condition by category, on the unified business model',
    intelligenceSection: 'Intelligence layers',
    intelligenceSubtitle: 'Headline verdict from each layer — select one to open it',
    chartSection: 'Live trends',
    chartSubtitle: 'Rolling window across the estate',
    alertSection: 'Recent alerts',
    activitySection: 'Activity',
    activitySubtitle: 'What the platform has observed most recently',
  },

  anomaly: {
    title: 'Anomaly Detection',
    subtitle: 'Layer 1 — abnormal behaviour across the estate',
    runAction: 'Run analysis',
  },

  predictive: {
    title: 'Predictive Maintenance',
    subtitle: 'Layer 2 — failure forecasts, with Layer 3 service scheduling',
    runAction: 'Recompute predictions',
  },

  oee: {
    title: 'Overall Equipment Efficiency',
    subtitle: 'Layer 6 — availability × performance × quality',
  },

  apm: {
    title: 'Asset Performance Management',
    subtitle: 'Layer 5 — reliability engineering and business value',
    reliabilityBand: 'Reliability engineering',
    businessBand: 'Business intelligence',
  },

  alerts: {
    title: 'Alerts',
    subtitle: 'Operator queue — severity and lifecycle filter independently',
    acknowledge: 'Acknowledge',
    resolve: 'Resolve',
    dismiss: 'Dismiss',
    assign: 'Assign',
  },

  reports: {
    title: 'Reports',
    subtitle: 'Generate and export platform records',
  },

  settings: {
    title: 'Settings',
    subtitle: 'Platform preferences and data source control',
  },

  assets: {
    title: 'Asset Registry',
    subtitle: 'Every monitored device and its live condition',
  },

  energy: {
    title: 'Energy Analytics',
    subtitle: 'Consumption, cost and metering coverage',
  },

  /**
   * Error codes to user-facing copy. The API never returns stack traces, so
   * this map is how a failure becomes something a person can act on.
   */
  errors: {
    RESOURCE_NOT_FOUND: 'That record no longer exists.',
    VALIDATION_FAILED: 'Some values were not accepted. Check the highlighted fields.',
    INVALID_STATE: 'That action is not available in the current state.',
    RESOURCE_CONFLICT: 'This conflicts with the record’s current state.',
    DATA_SOURCE_UNAVAILABLE: 'The data source is not running.',
    INTERNAL_ERROR: 'An unexpected error occurred. The incident has been logged.',
    NETWORK_ERROR: 'Cannot reach the platform. Check that the backend is running.',
    UNKNOWN_ERROR: 'Something went wrong.',
  } as Record<string, string>,
} as const

/** Resolve an API error code to display copy. */
export function errorMessage(code: string, fallback?: string): string {
  return STRINGS.errors[code] ?? fallback ?? STRINGS.errors.UNKNOWN_ERROR
}

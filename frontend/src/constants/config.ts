/**
 * Runtime configuration.
 *
 * Vite inlines `VITE_*` variables at build time, which would force one image
 * per environment. In containers the entrypoint writes `/config.js` before
 * nginx starts, and this module prefers that over the compiled defaults — so a
 * single built artefact can be promoted from development to production.
 */

interface RuntimeConfig {
  apiBaseUrl: string
  wsUrl: string
}

declare global {
  interface Window {
    __INTELORA_CONFIG__?: Partial<RuntimeConfig>
  }
}

function resolve(): RuntimeConfig {
  const injected = typeof window !== 'undefined' ? window.__INTELORA_CONFIG__ : undefined

  const apiBaseUrl =
    injected?.apiBaseUrl ??
    import.meta.env.VITE_API_BASE_URL ??
    'http://localhost:8000'

  const wsUrl =
    injected?.wsUrl ??
    import.meta.env.VITE_WS_URL ??
    apiBaseUrl.replace(/^http/, 'ws') + '/ws/live'

  return {
    apiBaseUrl: apiBaseUrl.replace(/\/+$/, ''),
    wsUrl,
  }
}

const runtime = resolve()

export const config = {
  ...runtime,
  apiPrefix: '/api/v1',

  /** Absolute URL for an API path. */
  api(path: string): string {
    return `${runtime.apiBaseUrl}${config.apiPrefix}${path}`
  },

  /** Absolute URL for a non-versioned root path such as `/health`. */
  root(path: string): string {
    return `${runtime.apiBaseUrl}${path}`
  },
} as const

/** Brand and shell constants fixed by the design system. */
export const BRAND = {
  name: 'INTELORA',
  tagline: 'Enterprise AIOT Intelligence Platform',
  /** Splash duration in milliseconds, within the 4–5s specification. */
  splashDurationMs: 4600,
  storageKeys: {
    theme: 'intelora.theme',
    sidebar: 'intelora.sidebar.collapsed',
  },
} as const

/** Shell dimensions, mirroring the CSS custom properties. */
export const LAYOUT = {
  navbarHeight: 72,
  sidebarWidth: 280,
  sidebarCollapsedWidth: 76,
} as const

/**
 * Live-stream tuning.
 *
 * The twin emits at 1 Hz. Rendering every message directly would re-render the
 * whole Cockpit on each one; instead messages are buffered and flushed on an
 * animation frame, so React does at most one pass per painted frame.
 */
export const LIVE = {
  reconnectBaseMs: 1000,
  reconnectMaxMs: 20000,
  heartbeatMs: 25000,
  /** Raw telemetry rows retained client-side for the live feed. */
  telemetryBuffer: 60,
} as const

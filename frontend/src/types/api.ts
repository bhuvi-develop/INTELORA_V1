/**
 * Transport-level contracts.
 *
 * Every INTELORA endpoint answers with the same envelope, and `status` is a
 * boolean *inside the body* — independent of the HTTP status code. A `200` can
 * therefore carry `status: false`. The HTTP client unwraps this and throws, so
 * no component ever sees an `Envelope`.
 */

/** A single machine-readable failure. */
export interface ApiError {
  /** Stable across releases; the UI maps it to copy rather than showing `message`. */
  code: string
  message: string
  field?: string | null
}

/** The uniform response body returned by every endpoint. */
export interface Envelope<T> {
  status: boolean
  message: string
  timestamp: string
  data: T | null
  errors: ApiError[]
}

export interface PageMeta {
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

/**
 * A single page of a collection. Telemetry retention is unlimited, so every
 * collection is paginated and no view may assume it holds a complete set.
 */
export interface Page<T> {
  items: T[]
  meta: PageMeta
}

/** Parameters accepted by every paginated endpoint. */
export interface PageQuery {
  page?: number
  page_size?: number
}

/** An explicit, closed time window. Required wherever history is queried. */
export interface WindowQuery {
  minutes?: number
  start?: string
  end?: string
}

/** Sort direction shared by every sortable table. */
export type SortDirection = 'asc' | 'desc'

/**
 * Error thrown by the HTTP client for any failure — transport, HTTP status, or
 * an envelope carrying `status: false`. Carrying the code lets callers branch
 * without parsing prose.
 */
export class InteloraApiError extends Error {
  readonly code: string
  readonly status: number
  readonly errors: ApiError[]

  constructor(message: string, options: { code?: string; status?: number; errors?: ApiError[] } = {}) {
    super(message)
    this.name = 'InteloraApiError'
    this.code = options.code ?? 'UNKNOWN_ERROR'
    this.status = options.status ?? 0
    this.errors = options.errors ?? []
  }

  /** True when the failure is a lost connection rather than a rejected request. */
  get isOffline(): boolean {
    return this.status === 0
  }
}

/** Liveness payload from `/health`. Not enveloped — probes expect it flat. */
export interface HealthCheck {
  status: string
  version: string
  environment: string
  database_connected: boolean
  twin_running: boolean
  timestamp: string
}

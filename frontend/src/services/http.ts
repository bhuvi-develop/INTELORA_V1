/**
 * HTTP client.
 *
 * Exists for one reason above all others: INTELORA's response envelope carries
 * `status` as a boolean *inside the body*, independent of the HTTP status code.
 * A `200 OK` can therefore carry `status: false`. Left unhandled, `fetch`
 * resolves, React Query records a success, and the failure reaches components
 * as empty data rather than an error state.
 *
 * This module unwraps the envelope and throws on `status: false`, so React
 * Query's error path works as intended and no component ever sees an
 * `Envelope`.
 *
 * The interceptor chain is deliberate groundwork: authentication is a later
 * phase, and attaching bearer tokens plus handling 401-refresh must not mean
 * editing every call site.
 */

import { config } from '@/constants/config'
import { errorMessage } from '@/constants/strings'
import { InteloraApiError, type Envelope } from '@/types/api'

type RequestInterceptor = (init: RequestInit & { url: string }) => RequestInit & { url: string }
type ErrorInterceptor = (error: InteloraApiError) => void

const requestInterceptors: RequestInterceptor[] = []
const errorInterceptors: ErrorInterceptor[] = []

/** Register a request transform. Reserved for token attachment. */
export function addRequestInterceptor(interceptor: RequestInterceptor): void {
  requestInterceptors.push(interceptor)
}

/** Register a failure observer, for global toasts or refresh handling. */
export function addErrorInterceptor(interceptor: ErrorInterceptor): void {
  errorInterceptors.push(interceptor)
}

function notify(error: InteloraApiError): InteloraApiError {
  for (const interceptor of errorInterceptors) {
    try {
      interceptor(error)
    } catch {
      // An interceptor must never mask the original failure.
    }
  }
  return error
}

/** Serialise query parameters, dropping empty values so URLs stay clean. */
export function toQuery(params: Record<string, unknown> | undefined): string {
  if (!params) return ''
  const search = new URLSearchParams()

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      value.forEach((entry) => search.append(key, String(entry)))
    } else {
      search.append(key, String(value))
    }
  }

  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  params?: Record<string, unknown>
  signal?: AbortSignal
  /** Bypass envelope unwrapping, for endpoints such as `/health`. */
  raw?: boolean
}

async function execute<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, params, signal, raw = false } = options

  let init: RequestInit & { url: string } = {
    url: `${url}${toQuery(params)}`,
    method,
    headers: { Accept: 'application/json' },
    ...(signal ? { signal } : {}),
  }

  if (body !== undefined) {
    init.headers = { ...init.headers, 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }

  for (const interceptor of requestInterceptors) {
    init = interceptor(init)
  }

  const { url: finalUrl, ...requestInit } = init

  let response: Response
  try {
    response = await fetch(finalUrl, requestInit)
  } catch (cause) {
    // Status 0 marks a transport failure — the platform is unreachable, which
    // is a different situation from a request the platform rejected.
    throw notify(
      new InteloraApiError(errorMessage('NETWORK_ERROR'), {
        code: 'NETWORK_ERROR',
        status: 0,
        errors: [{ code: 'NETWORK_ERROR', message: String(cause) }],
      }),
    )
  }

  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (raw) {
    if (!response.ok) {
      throw notify(
        new InteloraApiError(`Request failed with status ${response.status}.`, {
          status: response.status,
        }),
      )
    }
    return payload as T
  }

  const envelope = payload as Envelope<T> | null

  // Both failure modes converge here: a non-2xx response, and a 2xx response
  // whose envelope reports failure.
  if (!response.ok || !envelope || envelope.status === false) {
    const first = envelope?.errors?.[0]
    const code = first?.code ?? 'UNKNOWN_ERROR'
    throw notify(
      new InteloraApiError(errorMessage(code, envelope?.message), {
        code,
        status: response.status,
        errors: envelope?.errors ?? [],
      }),
    )
  }

  return envelope.data as T
}

/** Typed client for the versioned API. */
export const http = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    execute<T>(config.api(path), { ...options, method: 'GET' }),

  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    execute<T>(config.api(path), { ...options, method: 'POST', body }),

  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    execute<T>(config.api(path), { ...options, method: 'PUT', body }),

  delete: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    execute<T>(config.api(path), { ...options, method: 'DELETE' }),

  /** Non-versioned root paths, unwrapped, such as `/health`. */
  root: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    execute<T>(config.root(path), { ...options, method: 'GET', raw: true }),
}

/**
 * Download a file response.
 *
 * Report exports return a document rather than an envelope, so they bypass the
 * unwrapping path entirely and stream straight to the browser.
 */
export async function download(
  path: string,
  params: Record<string, unknown>,
  filename: string,
): Promise<void> {
  const response = await fetch(`${config.api(path)}${toQuery(params)}`, { method: 'POST' })

  if (!response.ok) {
    throw new InteloraApiError('The export could not be generated.', {
      code: 'EXPORT_FAILED',
      status: response.status,
    })
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

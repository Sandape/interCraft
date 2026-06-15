/**
 * Fetch client with interceptors and silent-refresh retry.
 *
 * - Attaches `Authorization: Bearer <access>` from token-storage.
 * - On 401, attempts ONE silent refresh, then replays the original
 *   request with the new access token. On second 401, clears tokens
 *   and surfaces a `TokenInvalidError`.
 * - Adds `X-Request-ID` and `X-Device-Fingerprint` to every request.
 * - 5xx responses are retried at most 2 times with exponential backoff
 *   (only for idempotent verbs: GET / HEAD).
 */
import { env, newRequestId } from './env'
import {
  ApiError,
  NetworkError,
  RateLimitError,
  TokenInvalidError,
  ValidationError,
  classifyBackendError,
  type FieldError,
} from './errors'
import { deviceFingerprint } from './device-fingerprint'
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from './token-storage'

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export interface RequestOptions {
  method: Method
  path: string
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
  skipAuth?: boolean
  signal?: AbortSignal
}

const SAFE_RETRY_METHODS = new Set<Method>(['GET'])

let refreshInFlight: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (env.USE_MOCK) return false
  const refresh = getRefreshToken()
  if (!refresh) return false
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${env.API_BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Request-ID': newRequestId(),
          'X-Device-Fingerprint': deviceFingerprint(),
        },
        body: JSON.stringify({ refresh_token: refresh }),
      })
      if (!res.ok) {
        clearTokens()
        return false
      }
      const data = (await res.json()) as { access_token: string; refresh_token: string }
      setTokens(data)
      return true
    } catch {
      clearTokens()
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  // `new URL(input, base)` needs a base when input is relative. In dev with
  // VITE_API_BASE_URL="" (default), we fall back to the page's origin so the
  // Vite dev server proxy can forward the request.
  const isAbsolute = path.startsWith('http')
  const joined = isAbsolute ? path : `${env.API_BASE_URL}${path}`
  const base = isAbsolute ? undefined : env.API_BASE_URL || window.location.origin
  const url = new URL(joined, base)
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined) continue
      url.searchParams.set(k, String(v))
    }
  }
  return url.toString()
}

function isEnveloped(body: unknown): body is { error: { code: string; message: string; request_id?: string; details?: Record<string, unknown> } } {
  return typeof body === 'object' && body !== null && 'error' in body
}

function backoffMs(attempt: number): number {
  // 200ms, 600ms — small but with jitter
  return 200 * Math.pow(3, attempt) + Math.floor(Math.random() * 100)
}

/** Overload: object form — `request({ method: 'GET', path: '/foo' })` */
export async function request<T>(opts: RequestOptions): Promise<T>
/** Overload: positional form — `request('GET', '/foo')` */
export async function request<T>(method: RequestOptions['method'], path: string, body?: unknown): Promise<T>
export async function request<T>(
  methodOrOpts: RequestOptions['method'] | RequestOptions,
  pathOrUndefined?: string,
  body?: unknown,
): Promise<T> {
  const opts: RequestOptions = typeof methodOrOpts === 'object'
    ? { ...methodOrOpts }
    : { method: methodOrOpts, path: pathOrUndefined!, body }
  const { method, path, body: optsBody, query, skipAuth, signal } = opts
  const effectiveBody = body !== undefined ? body : optsBody
  const requestId = newRequestId()
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Request-ID': requestId,
    'X-Device-Fingerprint': deviceFingerprint(),
  }
  if (effectiveBody !== undefined) headers['Content-Type'] = 'application/json'
  if (!skipAuth) {
    const access = getAccessToken()
    if (access) headers['Authorization'] = `Bearer ${access}`
  }

  const url = buildUrl(path, query)
  const hadAuth = !skipAuth && Boolean(headers['Authorization'])

  let attempt = 0
  // 5xx retry loop (max 2 retries → 3 attempts)
  // eslint-disable-next-line no-constant-condition
  while (true) {
    let res: Response
    try {
      res = await fetch(url, {
        method,
        headers,
        body: effectiveBody === undefined ? undefined : JSON.stringify(effectiveBody),
        signal,
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'network error'
      throw new NetworkError(msg)
    }

    // 401 → silent refresh + retry once. Only for requests that *had* an
    // Authorization header — login / register / refresh themselves should
    // surface the server's error directly.
    if (res.status === 401 && hadAuth && !skipAuth) {
      const refreshed = await tryRefresh()
      if (refreshed) {
        const access = getAccessToken()
        if (access) headers['Authorization'] = `Bearer ${access}`
        continue
      }
      clearTokens()
      const errBody = await safeJson(res)
      const rid = res.headers.get('X-Request-ID') ?? requestId
      throw new TokenInvalidError({
        message: (errBody as { error?: { message?: string } })?.error?.message ?? 'Unauthorized',
        requestId: rid,
        details: (errBody as { error?: { details?: Record<string, unknown> } })?.error?.details,
      })
    }

    // 5xx → retry (idempotent only)
    if (res.status >= 500 && SAFE_RETRY_METHODS.has(method) && attempt < 2) {
      attempt += 1
      await new Promise((r) => setTimeout(r, backoffMs(attempt)))
      continue
    }

    if (res.ok) {
      // 204 No Content
      if (res.status === 204) return undefined as T
      const ct = res.headers.get('Content-Type') ?? ''
      if (ct.includes('application/json')) {
        return (await res.json()) as T
      }
      return (await res.text()) as unknown as T
    }

    // Error path
    const errBody2 = await safeJson(res)
    const rid = res.headers.get('X-Request-ID') ?? requestId
    if (isEnveloped(errBody2)) {
      const err = errBody2.error
      if (res.status === 422) {
        const fieldErrors = ((err.details?.field_errors as FieldError[] | undefined) ?? [])
        throw new ValidationError({
          message: err.message,
          requestId: err.request_id ?? rid,
          details: err.details,
          fieldErrors,
        })
      }
      if (res.status === 429) {
        const retryAfter = Number(res.headers.get('Retry-After') ?? '0')
        throw new RateLimitError({
          message: err.message,
          requestId: err.request_id ?? rid,
          details: err.details,
          retryAfter: Number.isFinite(retryAfter) ? retryAfter : undefined,
        })
      }
      throw new ApiError({
        status: res.status,
        code: err.code,
        message: err.message,
        requestId: err.request_id ?? rid,
        details: err.details,
      })
    }
    // Non-enveloped error
    throw classifyBackendError(res.status, errBody2, rid)
  }
}

async function safeJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return null
  }
}

export const apiClient = { request }

export function withMock<TReal, TMock>(real: () => Promise<TReal>, mock: () => TMock): () => Promise<TReal | TMock> {
  return async () => (env.USE_MOCK ? mock() : real())
}

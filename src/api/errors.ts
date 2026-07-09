/**
 * Frontend error taxonomy. Mirrors the backend's `events.md` §5 envelope:
 *   { error: { code, message, request_id, details? } }
 *
 * Repositories throw one of these; the global error boundary / toast
 * surface renders the `code` + `message`.
 */

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string
  readonly details?: Record<string, unknown>

  constructor(opts: {
    status: number
    code: string
    message: string
    requestId: string
    details?: Record<string, unknown>
  }) {
    super(opts.message)
    this.name = 'ApiError'
    this.status = opts.status
    this.code = opts.code
    this.requestId = opts.requestId
    this.details = opts.details
  }
}

export class AuthError extends ApiError {
  constructor(opts: { message: string; requestId: string; details?: Record<string, unknown>; code?: string }) {
    super({
      status: 401,
      code: opts.code ?? 'auth.unauthenticated',
      message: opts.message,
      requestId: opts.requestId,
      details: opts.details,
    })
    this.name = 'AuthError'
  }
}

export class TokenInvalidError extends AuthError {
  constructor(opts: { message: string; requestId: string; details?: Record<string, unknown> }) {
    super({ ...opts, code: 'auth.token_invalid' })
    this.name = 'TokenInvalidError'
  }
}

export class SessionEvictedError extends AuthError {
  constructor(opts: { message: string; requestId: string; details?: Record<string, unknown> }) {
    super({ ...opts, code: 'auth.session_evicted' })
    this.name = 'SessionEvictedError'
  }
}

export class TokenExpiredError extends AuthError {
  // BUG #1 fix 2026-07-06: the backend now distinguishes
  // `auth.token_expired` from `auth.token_invalid` (which is reserved
  // for malformed / revoked tokens). Frontend callers can branch on
  // `instanceof TokenExpiredError` to surface a "please re-login"
  // toast instead of a generic auth error.
  constructor(opts: { message: string; requestId: string; details?: Record<string, unknown> }) {
    super({ ...opts, code: 'auth.token_expired' })
    this.name = 'TokenExpiredError'
  }
}

export class ValidationError extends ApiError {
  readonly fieldErrors: FieldError[]

  constructor(
    opts: { message: string; requestId: string; details?: Record<string, unknown>; fieldErrors?: FieldError[]; code?: string },
  ) {
    super({
      status: 422,
      code: opts.code ?? 'validation.failed',
      message: opts.message,
      requestId: opts.requestId,
      details: opts.details,
    })
    this.name = 'ValidationError'
    this.fieldErrors = opts.fieldErrors ?? []
  }
}

export class RateLimitError extends ApiError {
  readonly retryAfter: number | undefined

  constructor(opts: { message: string; requestId: string; details?: Record<string, unknown>; retryAfter?: number }) {
    super({
      status: 429,
      code: 'rate_limit.exceeded',
      message: opts.message,
      requestId: opts.requestId,
      details: opts.details,
    })
    this.name = 'RateLimitError'
    this.retryAfter = opts.retryAfter
  }
}

export class NetworkError extends ApiError {
  constructor(message: string) {
    super({
      status: 0,
      code: 'network.error',
      message,
      requestId: '',
    })
    this.name = 'NetworkError'
  }
}

export interface ApiErrorOpts {
  status: number
  code: string
  message: string
  requestId: string
  details?: Record<string, unknown>
}

export interface FieldError {
  field: string
  code: string
  message: string
}

export function classifyBackendError(
  status: number,
  body: unknown,
  requestId: string,
): ApiError {
  const envelope = (body as { error?: { code?: string; message?: string; details?: Record<string, unknown> } })?.error
  const code = envelope?.code ?? `http.${status}`
  const message = envelope?.message ?? `HTTP ${status}`
  const details = envelope?.details

  if (status === 401) {
    if (code === 'auth.token_invalid') return new TokenInvalidError({ message, requestId, details })
    if (code === 'auth.token_expired') return new TokenExpiredError({ message, requestId, details })
    if (code === 'auth.session_evicted') return new SessionEvictedError({ message, requestId, details })
    return new AuthError({ code, message, requestId, details })
  }
  if (status === 422) {
    const fieldErrors = ((details?.field_errors as FieldError[] | undefined) ?? [])
    return new ValidationError({ code, message, requestId, details, fieldErrors })
  }
  if (status === 429) {
    return new RateLimitError({ message, requestId, details })
  }
  return new ApiError({ status, code, message, requestId, details })
}

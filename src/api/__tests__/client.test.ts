import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { request } from '../client'
import { ValidationError } from '../errors'
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '../token-storage'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('api client auth refresh', () => {
  beforeEach(() => {
    clearTokens()
    window.sessionStorage.clear()
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    clearTokens()
  })

  it('unwraps backend refresh envelopes before replaying a 401 request', async () => {
    setTokens({ access_token: 'old-access', refresh_token: 'old-refresh' })
    const seenHeaders: Record<string, string>[] = []
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      seenHeaders.push({ ...((init?.headers ?? {}) as Record<string, string>) })
      if (seenHeaders.length === 1) {
        return jsonResponse({ error: { message: 'expired' } }, 401)
      }
      if (seenHeaders.length === 2) {
        return jsonResponse({
          tokens: {
            access_token: 'new-access',
            refresh_token: 'new-refresh',
          },
        })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      request<{ ok: boolean }>({ method: 'GET', path: '/api/v1/protected' }),
    ).resolves.toEqual({ ok: true })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(seenHeaders[0]).toMatchObject({
      Authorization: 'Bearer old-access',
    })
    expect(seenHeaders[2]).toMatchObject({
      Authorization: 'Bearer new-access',
    })
    expect(getAccessToken()).toBe('new-access')
    expect(getRefreshToken()).toBe('new-refresh')
  })

  it('does NOT clear tokens on 5xx from refresh endpoint (FR-005)', async () => {
    setTokens({ access_token: 'keep-access', refresh_token: 'keep-refresh' })
    let attempt = 0
    const fetchMock = vi.fn(async () => {
      attempt++
      if (attempt === 1) {
        // First call triggers 401 → tryRefresh is attempted
        return jsonResponse({ error: { message: 'expired' } }, 401)
      }
      // Refresh endpoint returns 502
      return new Response('Service Unavailable', { status: 502 })
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      request<{ ok: boolean }>({ method: 'GET', path: '/api/v1/protected' }),
    ).rejects.toThrow()

    // Tokens must be preserved after a 502 from the refresh endpoint.
    expect(getAccessToken()).toBe('keep-access')
    expect(getRefreshToken()).toBe('keep-refresh')
  })

  it('does NOT clear tokens on network error from refresh (FR-005)', async () => {
    setTokens({ access_token: 'net-access', refresh_token: 'net-refresh' })
    let attempt = 0
    const fetchMock = vi.fn(async () => {
      attempt++
      if (attempt === 1) {
        return jsonResponse({ error: { message: 'expired' } }, 401)
      }
      // Network error (fetch throws)
      throw new TypeError('Failed to fetch')
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      request<{ ok: boolean }>({ method: 'GET', path: '/api/v1/protected' }),
    ).rejects.toThrow()

    // Tokens must survive a network error during refresh.
    expect(getAccessToken()).toBe('net-access')
    expect(getRefreshToken()).toBe('net-refresh')
  })

  it('still clears tokens on definitive auth error during refresh (FR-005)', async () => {
    setTokens({ access_token: 'clear-access', refresh_token: 'clear-refresh' })
    let attempt = 0
    const fetchMock = vi.fn(async () => {
      attempt++
      if (attempt === 1) {
        return jsonResponse({ error: { message: 'expired' } }, 401)
      }
      // Backend says token is invalid (definitive).
      return jsonResponse({ error: { code: 'auth.token_invalid', message: 'Token invalid' } }, 401)
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      request<{ ok: boolean }>({ method: 'GET', path: '/api/v1/protected' }),
    ).rejects.toThrow()

    // Tokens MUST be cleared for definitive auth errors.
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })

  it('preserves backend 422 business codes on ValidationError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({
      error: {
        code: 'INSUFFICIENT_ERROR_POOL',
        message: 'Not enough active error questions for quick drill',
        request_id: 'req-048',
        details: { available: 0, required: 5 },
      },
    }, 422)))

    await expect(
      request({ method: 'POST', path: '/api/v1/interview-sessions', body: {} }),
    ).rejects.toMatchObject({
      name: 'ValidationError',
      code: 'INSUFFICIENT_ERROR_POOL',
      requestId: 'req-048',
      details: { available: 0, required: 5 },
    })

    await expect(
      request({ method: 'POST', path: '/api/v1/interview-sessions', body: {} }),
    ).rejects.toBeInstanceOf(ValidationError)
  })
})

import { beforeEach, describe, expect, it } from 'vitest'
import { clearTokens, getAccessToken } from '../token-storage'
import { AuthError, classifyBackendError, SessionEvictedError } from '../errors'

describe('token-storage', () => {
  beforeEach(() => {
    clearTokens()
    window.sessionStorage.clear()
    window.localStorage.clear()
  })

  it('falls back to the legacy access-token mirror when sessionStorage is empty', () => {
    window.localStorage.setItem('access_token', 'mirror-access-token')

    expect(getAccessToken()).toBe('mirror-access-token')
  })
})

describe('SessionEvictedError', () => {
  it('returns SessionEvictedError from classifyBackendError for auth.session_evicted code', () => {
    const err = classifyBackendError(
      401,
      { error: { code: 'auth.session_evicted', message: 'Session evicted' } },
      'req-123',
    )
    expect(err).toBeInstanceOf(SessionEvictedError)
    expect(err.code).toBe('auth.session_evicted')
  })

  it('returns generic AuthError for unknown auth codes', () => {
    const err = classifyBackendError(
      401,
      { error: { code: 'auth.unknown_code', message: 'Something else' } },
      'req-456',
    )
    expect(err).toBeInstanceOf(AuthError)
    expect(err.code).toBe('auth.unknown_code')
  })
})

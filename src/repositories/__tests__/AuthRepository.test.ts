/**
 * Smoke tests for AuthRepository using MSW to mirror the backend.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { HttpAuthRepository } from '../AuthRepository'
import { clearTokens, getAccessToken } from '../../api/token-storage'

describe('HttpAuthRepository', () => {
  beforeEach(() => {
    clearTokens()
  })

  it('register returns user and tokens (storage is done by mutation hook)', async () => {
    const repo = new HttpAuthRepository()
    const res = await repo.register({
      email: 'test@intercraft.io',
      password: 'P@ssw0rd123',
      display_name: 'Test',
      device_fingerprint: 'fp-test',
    })
    expect(res.user.email).toBe('test@intercraft.io')
    expect(res.tokens.access_token).toBe('mock-access-token')
  })

  it('login returns 401 for bad credentials', async () => {
    const repo = new HttpAuthRepository()
    await expect(
      repo.login({ email: 'wrong@intercraft.io', password: 'Demo1234', device_fingerprint: 'fp' }),
    ).rejects.toMatchObject({ code: 'auth.invalid_credentials', status: 401 })
  })

  it('login happy path', async () => {
    const repo = new HttpAuthRepository()
    const res = await repo.login({
      email: 'demo@intercraft.io',
      password: 'Demo1234',
      device_fingerprint: 'fp',
    })
    expect(res.user.email).toBe('demo@intercraft.io')
  })

  it('register rejects taken email with 409', async () => {
    const repo = new HttpAuthRepository()
    await expect(
      repo.register({
        email: 'taken@intercraft.io',
        password: 'P@ssw0rd123',
        device_fingerprint: 'fp',
      }),
    ).rejects.toMatchObject({ code: 'auth.email_taken', status: 409 })
  })
})

/**
 * Round-1 shared fixtures: user registration + token injection.
 *
 * Each test creates a fresh user so cases are isolated; tokens go into
 * sessionStorage so existing axios interceptors pick them up.
 */
import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const PASSWORD = 'P@ssw0rd1234'
export const API_BASE = process.env.E2E_API_BASE ?? 'http://127.0.0.1:8000'
export const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://127.0.0.1:5173'

export interface User {
  email: string
  password: string
  display_name: string
  access_token: string
  user_id: string
}

export function makeEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}@intercraft-e2e.com`
}

export async function registerUser(
  request: APIRequestContext,
  prefix = 'e2e-round1',
): Promise<User> {
  const email = makeEmail(prefix)
  const res = await request.post(`${API_BASE}/api/v1/auth/register`, {
    data: { email, password: PASSWORD, display_name: 'Round1 E2E' },
  })
  expect([200, 201]).toContain(res.status())
  const body = await res.json()
  const access_token = body.tokens?.access_token || body.access_token
  const user_id = body.user?.id
  expect(access_token).toBeTruthy()
  expect(user_id).toBeTruthy()
  return { email, password: PASSWORD, display_name: 'Round1 E2E', access_token, user_id }
}

export async function injectToken(page: Page, token: string): Promise<void> {
  await page.addInitScript((t: string) => {
    sessionStorage.setItem('ic.access_token', t)
    sessionStorage.setItem('ic.refresh_token', t)
  }, token)
}

export async function registerAndAuthenticate(
  request: APIRequestContext,
  page: Page,
  prefix = 'e2e-round1',
): Promise<User> {
  const user = await registerUser(request, prefix)
  await injectToken(page, user.access_token)
  return user
}

/**
 * REQ-044 IA — AC-3.2 / FR-003
 *
 * PM 角色登录 admin 后，访问 /admin-console / /admin-console/
 * 必须重定向到 /admin-console/command-center (5xx 内通过)。
 */
import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://127.0.0.1:5305'
const BACKEND_BASE = process.env.E2E_BACKEND_BASE ?? 'http://127.0.0.1:8205'
const DEMO_EMAIL = 'demo@intercraft.io'
const DEMO_PASSWORD = 'Demo1234'

async function loginAsDemo(page: Page, request: APIRequestContext) {
  const res = await request.post(`${BACKEND_BASE}/api/v1/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  })
  expect(res.status(), `POST /auth/login → ${res.status()}`).toBeLessThan(400)
  const body = await res.json()
  const tokens = body.tokens as { access_token: string; refresh_token: string }

  await page.addInitScript(({ access, refresh }) => {
    window.sessionStorage.setItem('ic.access_token', access)
    window.sessionStorage.setItem('ic.refresh_token', refresh)
    window.localStorage.setItem('access_token', access)
  }, { access: tokens.access_token, refresh: tokens.refresh_token })
}

test.describe('REQ-044 IA — PM landing = command-center', () => {
  test('/admin-console redirects to /admin-console/command-center', async ({ page, request }) => {
    await loginAsDemo(page, request)
    await page.goto(`${FRONTEND_BASE}/index.admin.html`, { waitUntil: 'domcontentloaded' })
    await expect(page).toHaveURL(/\/admin-console\/command-center/, { timeout: 20_000 })
    await expect(page.getByTestId('command-center')).toBeVisible({ timeout: 20_000 })
  })
})
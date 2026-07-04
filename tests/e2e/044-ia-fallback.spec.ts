/**
 * REQ-044 IA — EC-3b / EC-3 / EC-4
 *
 * Playwright 实证 weird-role fallback: 注入 localStorage.auth-user
 * 含未知 role → refresh /admin-console → sidebar 至少 1 个 nav item
 * 且第一项含 command-center href.
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

test.describe('REQ-044 IA — weird role fallback', () => {
  test('unknown role → sidebar ≥ 1 item, first = command-center', async ({ page, request }) => {
    await loginAsDemo(page, request)
    // Override auth-user with a weird role BEFORE first navigation
    // so AdminShell.resolveRole() picks it up via localStorage.
    await page.addInitScript(() => {
      window.localStorage.setItem(
        'auth-user',
        JSON.stringify({ email: 'test@x', role: 'weird-role-not-in-union' }),
      )
    })

    await page.goto(`${FRONTEND_BASE}/index.admin.html`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.ac-shell__nav-item').first()).toBeVisible({ timeout: 20_000 })

    const links = page.locator('.ac-shell__nav-item')
    const count = await links.count()
    expect(count, 'weird role must still expose ≥ 1 nav item (command-center fallback)').toBeGreaterThanOrEqual(1)

    const firstHref = await links.first().getAttribute('href')
    expect(firstHref, `first item href must contain command-center, got ${firstHref}`).toContain('command-center')
  })
})
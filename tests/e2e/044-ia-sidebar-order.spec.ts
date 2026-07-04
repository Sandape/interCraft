/**
 * REQ-044 IA — AC-4.3 / FR-004
 *
 * PM 角色展开 sidebar，第一项必须是 Command Center，
 * 不允许 logs/traces 成为默认入口。
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

test.describe('REQ-044 IA — first visible nav item is Command Center', () => {
  test('first sidebar item = Command Center, NOT Logs/日志', async ({ page, request }) => {
    await loginAsDemo(page, request)
    await page.goto(`${FRONTEND_BASE}/index.admin.html`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.ac-shell__nav-item').first()).toBeVisible({ timeout: 20_000 })

    const firstItem = page.locator('.ac-shell__nav-item').first()
    const firstText = (await firstItem.textContent()) ?? ''
    const firstHref = await firstItem.getAttribute('href')

    // FR-004 first item must reference command-center.
    expect(firstHref, `first item href must contain command-center, got ${firstHref}`).toContain('command-center')
    // FR-004 logs/traces MUST NOT be the default.
    expect(firstText.toLowerCase(), `first item text must not contain 'log', got '${firstText}'`).not.toContain('log')
  })
})
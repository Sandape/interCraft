/**
 * REQ-044 IA — AC-2.5 / SC-FR-005
 *
 * PM 角色登录 admin 后，sidebar 必须渲染 8 个 NAV_LINK
 * (command-center / product-analytics / ai-operations /
 * incidents-badcases / logs-and-traces / users-accounts /
 * reports / governance). 旧 4-item shell 完全退出。
 */
import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://127.0.0.1:5305'
const BACKEND_BASE = process.env.E2E_BACKEND_BASE ?? 'http://127.0.0.1:8205'
const DEMO_EMAIL = 'demo@intercraft.io'
const DEMO_PASSWORD = 'Demo1234'

async function loginAndOpenAdmin(page: Page, request: APIRequestContext) {
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

  await page.goto(`${FRONTEND_BASE}/index.admin.html`, { waitUntil: 'domcontentloaded' })
  // Wait for the shell to render at least one nav item before counting.
  await expect(page.locator('.ac-shell__nav-item').first()).toBeVisible({ timeout: 20_000 })
}

test.describe('REQ-044 IA — 8 workspaces visible', () => {
  test('PM sidebar renders all 8 NAV_LINK items', async ({ page, request }) => {
    await loginAndOpenAdmin(page, request)

    const links = page.locator('.ac-shell__nav-item')
    const count = await links.count()
    expect(count, 'PM 角色必须看到 8 个 workspace nav item').toBeGreaterThanOrEqual(8)

    const expectedFragments = [
      'command-center',
      'product-analytics',
      'ai-operations',
      'incidents-badcases',
      'logs-and-traces',
      'users-accounts',
      'reports',
      'governance',
    ]
    const html = await page.locator('aside.ac-shell__sidebar').innerHTML()
    for (const frag of expectedFragments) {
      expect(html, `sidebar must reference ${frag}`).toContain(frag)
    }
  })
})
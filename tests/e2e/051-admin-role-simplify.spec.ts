/**
 * REQ-051 E2E — admin role simplification + localization.
 *
 * Covers:
 * - SC-001: admin entry to /admin-console in <= 2 clicks
 * - SC-002: non-admin redirected from /admin-console
 * - SC-003: Chinese labels visible in admin console shell
 * - FR-012: Topbar Shield button visible for admin
 * - FR-014: Sidebar admin link visible for admin
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

test.describe('REQ-051 — admin role simplification', () => {
  test('SC-001: admin user enters admin console in <= 2 clicks', async ({ page, request }) => {
    await loginAsDemo(page, request)
    await page.goto(`${FRONTEND_BASE}/dashboard`, { waitUntil: 'domcontentloaded' })

    // Click the Shield button in the Topbar (FR-012)
    const adminBtn = page.getByTestId('topbar-admin-console-button')
    await expect(adminBtn).toBeVisible({ timeout: 15_000 })
    await adminBtn.click()

    // Should land on command-center
    await expect(page).toHaveURL(/\/admin-console\/command-center/, { timeout: 20_000 })
    await expect(page.getByTestId('command-center')).toBeVisible({ timeout: 20_000 })
  })

  test('SC-003: admin console shell shows Chinese labels', async ({ page, request }) => {
    await loginAsDemo(page, request)
    await page.goto(`${FRONTEND_BASE}/admin-console/command-center`, { waitUntil: 'domcontentloaded' })

    // Verify Chinese navigation labels (FR-008)
    const nav = page.locator('.ac-shell__nav')
    await expect(nav).toBeVisible({ timeout: 15_000 })

    // The 8 workspace labels should be Chinese
    const zhLabels = ['指挥中心', '产品分析', 'AI 运营', '事件与差例', '日志与链路', '用户与账户', '报告中心', '治理与审计']
    for (const label of zhLabels) {
      await expect(nav.getByText(label, { exact: true })).toBeVisible({ timeout: 5_000 })
    }

    // Page title should be Chinese
    await expect(page.getByText('指挥中心')).toBeVisible({ timeout: 5_000 })
  })

  test('SC-002: non-admin visiting /admin-console gets redirected', async ({ page, request }) => {
    // Register a fresh non-admin user
    const suffix = Math.random().toString(36).slice(2, 8)
    const registerRes = await request.post(`${BACKEND_BASE}/api/v1/auth/register`, {
      data: {
        email: `e2e_051_${suffix}@intercraft.io`,
        password: 'Demo1234',
        display_name: `E2E 051 User ${suffix}`,
        device_fingerprint: `fp_051_${suffix}`,
      },
      headers: { 'X-Device-Fingerprint': `fp_051_${suffix}` },
    })
    expect(registerRes.status()).toBeLessThan(400)
    const body = await registerRes.json()
    const tokens = body.tokens as { access_token: string; refresh_token: string }

    // Verify this user is NOT admin
    expect(body.user?.is_admin).toBeFalsy()

    await page.addInitScript(({ access, refresh }) => {
      window.sessionStorage.setItem('ic.access_token', access)
      window.sessionStorage.setItem('ic.refresh_token', refresh)
      window.localStorage.setItem('access_token', access)
    }, { access: tokens.access_token, refresh: tokens.refresh_token })

    // Navigate to admin console — should be redirected
    await page.goto(`${FRONTEND_BASE}/admin-console/command-center`, { waitUntil: 'domcontentloaded' })

    // Should be redirected to /dashboard within 3 seconds (SC-002)
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 })
  })

  test('FR-014: sidebar admin link visible for admin user', async ({ page, request }) => {
    await loginAsDemo(page, request)
    await page.goto(`${FRONTEND_BASE}/dashboard`, { waitUntil: 'domcontentloaded' })

    // Check sidebar contains the admin link with Shield icon
    const sidebar = page.locator('aside')
    await expect(sidebar).toBeVisible({ timeout: 15_000 })

    // Find the admin link in the sidebar
    const adminLink = sidebar.getByText('管理后台')
    await expect(adminLink).toBeVisible({ timeout: 5_000 })

    // Click the admin link
    await adminLink.click()
    await expect(page).toHaveURL(/\/admin-console\/command-center/, { timeout: 20_000 })
  })
})

import { expect, test, type Page, type APIRequestContext } from '@playwright/test'

const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://127.0.0.1:5302'
const BACKEND_BASE = process.env.E2E_BACKEND_BASE ?? 'http://127.0.0.1:8202'
const DEMO_EMAIL = 'demo@intercraft.io'
const DEMO_PASSWORD = 'Demo1234'

async function loginTokens(request: APIRequestContext) {
  const res = await request.post(`${BACKEND_BASE}/api/v1/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  })
  expect(res.status(), `POST /auth/login → ${res.status()}`).toBeLessThan(400)
  const body = await res.json()
  return body.tokens as { access_token: string; refresh_token: string }
}

async function openAdminLogCenter(page: Page, request: APIRequestContext) {
  const tokens = await loginTokens(request)
  await page.addInitScript(({ access, refresh }) => {
    window.sessionStorage.setItem('ic.access_token', access)
    window.sessionStorage.setItem('ic.refresh_token', refresh)
    window.localStorage.setItem('access_token', access)
  }, { access: tokens.access_token, refresh: tokens.refresh_token })

  await page.goto(`${FRONTEND_BASE}/index.admin.html`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('log-center')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId('task-table')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByTestId('task-row').first()).toBeVisible({ timeout: 20_000 })
}

test.describe('REQ-039 Log Center full acceptance', () => {
  test('manual refresh renders list/detail and does not poll while idle', async ({ page, request }) => {
    await openAdminLogCenter(page, request)

    await page.getByTestId('task-row').first().click()
    await expect(page.getByTestId('detail-panel')).toBeVisible({ timeout: 10_000 })

    const refreshResponses: string[] = []
    page.on('request', (req) => {
      const url = req.url()
      if (url.includes('/api/v1/admin-console/observability/traces')) {
        refreshResponses.push(url)
      }
    })

    await page.getByTestId('refresh-btn').click()
    await expect(page.getByTestId('refresh-btn')).toBeEnabled({ timeout: 10_000 })
    expect(refreshResponses.some((url) => url.includes('/observability/traces'))).toBeTruthy()

    refreshResponses.length = 0
    await page.waitForTimeout(10_000)
    expect(refreshResponses, 'FR-005: no unsolicited traces fetches within 10s idle').toHaveLength(0)
  })

  test('tag dialog persists via backend and command palette opens', async ({ page, request }) => {
    await openAdminLogCenter(page, request)

    await page.getByTestId('task-row').first().click()
    await page.getByTestId('open-tags').first().click()
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10_000 })
    await page.getByTestId('tag-input').fill(`e2e-b3-${Date.now()}`)
    await page.getByTestId('tag-save').click()
    await expect(page.getByTestId('toast')).toContainText(/标签已保存|已保存|saved/i, { timeout: 10_000 })
    await page.getByTestId('modal-close').click()

    await page.getByTestId('open-palette').click()
    await expect(page.getByTestId('command-palette')).toBeVisible({ timeout: 10_000 })
  })

  test('diff dialog opens after selecting two traces and error aggregation renders', async ({ page, request }) => {
    await openAdminLogCenter(page, request)

    await expect(page.getByTestId('error-buckets').or(page.getByTestId('error-empty'))).toBeVisible({ timeout: 10_000 })

    const boxes = page.getByTestId('task-diff-checkbox')
    await expect(boxes.nth(0)).toBeVisible({ timeout: 10_000 })
    await boxes.nth(0).check()
    await boxes.nth(1).check()
    await page.getByTestId('open-diff').click()
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByTestId('diff-left')).toBeVisible()
    await expect(page.getByTestId('diff-right')).toBeVisible()
  })
})

import { expect, test, type Page } from '@playwright/test'

const USER = {
  id: 'user-search-recovery',
  email: 'search-recovery@intercraft.test',
  display_name: 'Search Recovery Tester',
  title: 'Frontend Engineer',
  years_of_experience: 5,
  target_role: 'Senior Frontend Engineer',
  bio: null,
  subscription: 'pro',
  created_at: '2026-06-16T00:00:00Z',
  updated_at: '2026-06-16T00:00:00Z',
}

const SESSIONS = [
  {
    id: 'session-alpha',
    mode: 'text',
    status: 'completed',
    position: 'Frontend Platform Engineer',
    company: 'InterCraft',
    score: 86,
    overall_score: 86,
    duration_seconds: 480,
    question_count: 5,
    thread_id: 'thread-alpha',
    created_at: '2026-06-16T00:00:00Z',
    updated_at: '2026-06-16T00:08:00Z',
  },
  {
    id: 'session-beta',
    mode: 'text',
    status: 'completed',
    position: 'Backend Infrastructure Engineer',
    company: 'Eggg Labs',
    score: 91,
    overall_score: 91,
    duration_seconds: 420,
    question_count: 5,
    thread_id: 'thread-beta',
    created_at: '2026-06-15T00:00:00Z',
    updated_at: '2026-06-15T00:07:00Z',
  },
]

async function authenticate(page: Page) {
  await page.addInitScript(() => {
    sessionStorage.setItem('ic.access_token', 'e2e-access-token')
    sessionStorage.setItem('ic.refresh_token', 'e2e-refresh-token')
  })
}

async function routeCommon(page: Page, sessions = SESSIONS) {
  await page.route('**/api/v1/users/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(USER) })
  })

  await page.route('**/api/v1/error-questions**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [] }) })
  })

  await page.route(/\/api\/v1\/interview-sessions(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: sessions }),
    })
  })
}

async function openInterview(page: Page) {
  const sessionsLoaded = page.waitForResponse((response) =>
    response.url().includes('/api/v1/interview-sessions') &&
    response.request().method() === 'GET' &&
    response.status() === 200,
  )
  await page.goto('/interview')
  await sessionsLoaded
  await page.waitForTimeout(500)
  await expect(page.locator('[data-testid="interview-search-input"]')).toBeVisible()
}

test.describe('Interview search recovery', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    await authenticate(page)
  })

  test('filters sessions by company and position', async ({ page }) => {
    await routeCommon(page)
    await openInterview(page)

    await expect(page.locator('[data-testid="session-card"][data-session-id="session-alpha"]')).toBeVisible()
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-beta"]')).toBeVisible()

    const search = page.locator('[data-testid="interview-search-input"]')
    await search.fill('intercraft')
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-alpha"]')).toBeVisible()
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-beta"]')).toHaveCount(0)

    await search.fill(' infrastructure ')
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-alpha"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-beta"]')).toBeVisible()
  })

  test('clears a no-result search and restores the full list', async ({ page }) => {
    await routeCommon(page)
    await openInterview(page)

    const search = page.locator('[data-testid="interview-search-input"]')
    await search.fill('no matching company')

    await expect(page.locator('[data-testid="interview-search-empty"]')).toBeVisible()
    await expect(page.locator('[data-testid="interview-search-empty-query"]')).toContainText('no matching company')
    await expect(page.locator('[data-testid="session-card"]')).toHaveCount(0)

    await page.locator('[data-testid="clear-interview-search"]').click()

    await expect(search).toHaveValue('')
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-alpha"]')).toBeVisible()
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-beta"]')).toBeVisible()
  })

  test('preserves true empty history guidance', async ({ page }) => {
    await routeCommon(page, [])
    await openInterview(page)

    await expect(page.locator('[data-testid="interview-history-empty"]')).toBeVisible()
    await expect(page.locator('[data-testid="interview-search-empty"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="clear-interview-search"]')).toHaveCount(0)
  })
})

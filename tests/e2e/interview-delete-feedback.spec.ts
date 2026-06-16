import { expect, test, type Page } from '@playwright/test'

const USER = {
  id: 'user-delete-feedback',
  email: 'delete-feedback@intercraft.test',
  display_name: 'Delete Feedback Tester',
  title: 'Frontend Engineer',
  years_of_experience: 5,
  target_role: 'Senior Frontend Engineer',
  bio: null,
  subscription: 'pro',
  created_at: '2026-06-16T00:00:00Z',
  updated_at: '2026-06-16T00:00:00Z',
}

const BASE_SESSIONS = [
  {
    id: 'session-delete-target',
    mode: 'text',
    status: 'completed',
    position: 'Frontend Platform Engineer',
    company: 'InterCraft',
    score: 86,
    overall_score: 86,
    duration_seconds: 480,
    question_count: 5,
    thread_id: 'thread-delete-target',
    created_at: '2026-06-16T00:00:00Z',
    updated_at: '2026-06-16T00:08:00Z',
  },
  {
    id: 'session-keep',
    mode: 'text',
    status: 'completed',
    position: 'React Engineer',
    company: 'Eggg Labs',
    score: 91,
    overall_score: 91,
    duration_seconds: 420,
    question_count: 5,
    thread_id: 'thread-keep',
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

async function routeCommon(page: Page, options?: { failFirstDelete?: boolean }) {
  let sessions = [...BASE_SESSIONS]
  let deleteAttempts = 0

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

  await page.route(/\/api\/v1\/interview-sessions\/[^/]+$/, async (route) => {
    if (route.request().method() !== 'DELETE') {
      await route.fallback()
      return
    }

    deleteAttempts += 1
    const id = route.request().url().split('/').pop()

    if (options?.failFirstDelete && deleteAttempts === 1) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'interview.delete_failed',
            message: 'Delete failed. Please retry.',
            request_id: 'delete-feedback-test',
          },
        }),
      })
      return
    }

    sessions = sessions.filter((session) => session.id !== id)
    await route.fulfill({ status: 204 })
  })

  return {
    getDeleteAttempts: () => deleteAttempts,
  }
}

test.describe('Interview delete feedback', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    await authenticate(page)
  })

  test('removes a session after confirmed delete', async ({ page }) => {
    await routeCommon(page)

    await page.goto('/interview')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-delete-target"]')).toBeVisible()

    const deleteButton = page.locator('[data-testid="delete-interview-session-delete-target"]')
    await expect(deleteButton).toBeVisible()
    await deleteButton.click()
    await expect(page.locator('[data-testid="delete-confirm-dialog"]')).toBeVisible()

    await page.locator('[data-testid="confirm-delete-btn"]').click()

    await expect(page.locator('[data-testid="delete-confirm-dialog"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-delete-target"]')).toHaveCount(0)
  })

  test('keeps the dialog open after delete failure and succeeds on retry', async ({ page }) => {
    await routeCommon(page, { failFirstDelete: true })

    await page.goto('/interview')
    await page.waitForLoadState('networkidle')
    const deleteButton = page.locator('[data-testid="delete-interview-session-delete-target"]')
    await expect(deleteButton).toBeVisible()
    await deleteButton.click()
    await page.locator('[data-testid="confirm-delete-btn"]').click()

    await expect(page.locator('[data-testid="delete-confirm-dialog"]')).toBeVisible()
    await expect(page.locator('[data-testid="delete-error-message"]')).toBeVisible()
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-delete-target"]')).toBeVisible()

    await page.locator('[data-testid="confirm-delete-btn"]').click()

    await expect(page.locator('[data-testid="delete-confirm-dialog"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-delete-target"]')).toHaveCount(0)
  })

  test('cancels deletion without sending a delete request', async ({ page }) => {
    const routes = await routeCommon(page)

    await page.goto('/interview')
    await page.waitForLoadState('networkidle')
    const deleteButton = page.locator('[data-testid="delete-interview-session-delete-target"]')
    await expect(deleteButton).toBeVisible()
    await deleteButton.click()
    await expect(page.locator('[data-testid="delete-confirm-dialog"]')).toBeVisible()

    await page.locator('[data-testid="cancel-delete-btn"]').click()

    await expect(page.locator('[data-testid="delete-confirm-dialog"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="session-card"][data-session-id="session-delete-target"]')).toBeVisible()
    expect(routes.getDeleteAttempts()).toBe(0)
  })
})

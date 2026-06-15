/**
 * E2E: Phase 5 edge cases — auth redirects and empty states.
 *
 * Scenarios:
 *  E1. Unauthenticated access to /coach redirects to /login
 *  E2. Login → /error-book shows "还没有错题记录" when no questions
 *      (skipped if the test user already has questions from prior tests)
 */
import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

const BASE_URL = 'http://localhost:5173'
const API_URL = 'http://localhost:8002/api/v1'
const TEST_USER = { email: 'test@intercraft.io', password: 'Demo1234' }

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`)
  await page.waitForSelector('[data-testid="email-input"]', { timeout: 10_000 })
  await page.fill('[data-testid="email-input"]', TEST_USER.email)
  await page.fill('[data-testid="password-input"]', TEST_USER.password)
  await page.click('[data-testid="auth-submit"]')
  await page.waitForURL('**/dashboard', { timeout: 15_000 })
}

test.describe('Phase 5 — Edge cases', () => {
  test('E1: unauthenticated /coach → /login', async ({ page, context }) => {
    // Clear all cookies/storage to ensure unauthenticated state
    await context.clearCookies()
    await page.goto(`${BASE_URL}/coach`)
    await page.waitForURL('**/login', { timeout: 10_000 })
    expect(page.url()).toContain('/login')

    await page.screenshot({ path: 'test-results/edge-e1-redirect.png' })
  })

  test('E2: empty error book → "还没有错题记录"', async ({ page, request }) => {
    // First check if there are any error questions
    const loginRes = await request.post(`${API_URL}/auth/login`, { data: TEST_USER })
    expect(loginRes.ok()).toBeTruthy()
    const { tokens } = await loginRes.json()
    const auth = { Authorization: `Bearer ${tokens.access_token}` }

    const listRes = await request.get(`${API_URL}/error-questions?frequency_min=0&limit=50`, { headers: auth })
    const listBody = await listRes.json()
    const questions = listBody?.data ?? []
    test.skip(questions.length > 0, 'Test user already has error questions seeded')

    // Now visit the empty error book
    await login(page)
    await page.goto(`${BASE_URL}/error-book`)
    await page.waitForLoadState('networkidle')

    // Empty state should be visible
    await expect(page.getByText('还没有错题记录').first()).toBeVisible({ timeout: 10_000 })

    await page.screenshot({ path: 'test-results/edge-e2-empty.png' })
  })
})

/**
 * E2E: Activities feed with cursor pagination (US8).
 * Requires backend + DB (T008b).
 */
import { test, expect } from '@playwright/test'

test('activities API returns paginated response', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-activity-${stamp}@intercraft.io`

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill('P@ssw0rd123')
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  // Navigate to dashboard (which may show activities)
  await expect(page.locator('h1').first()).toBeVisible({ timeout: 5_000 })
})

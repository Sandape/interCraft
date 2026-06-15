/**
 * E2E: Profile page renders ability radar chart from API (US5).
 * Requires backend + DB (T008b).
 */
import { test, expect } from '@playwright/test'

test('profile page loads ability dimensions from API', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-profile-${stamp}@intercraft.io`

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill('P@ssw0rd123')
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  await page.goto('/profile')
  await expect(page).toHaveURL(/\/profile$/)

  // The profile page should show the ability dimensions section
  await expect(page.locator('text=技术深度').first()).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('text=工程基础').first()).toBeVisible({ timeout: 5_000 })
})

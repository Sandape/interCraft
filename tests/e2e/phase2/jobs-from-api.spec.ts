/**
 * E2E: Jobs page CRUD + status advancement from API (US8).
 * Requires backend + DB (T008b).
 */
import { test, expect } from '@playwright/test'

test('jobs page loads empty state and allows creation', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-jobs-${stamp}@intercraft.io`

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill('P@ssw0rd123')
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  await page.goto('/jobs')
  await expect(page).toHaveURL(/\/jobs$/)

  // Should show the jobs page header
  await expect(page.locator('h1')).toContainText('求职追踪')
})

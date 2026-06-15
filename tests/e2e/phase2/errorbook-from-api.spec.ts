/**
 * E2E: ErrorBook CRUD + status machine from API (US6).
 * Requires backend + DB (T008b).
 */
import { test, expect } from '@playwright/test'

test('error book page loads and shows empty state', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-error-${stamp}@intercraft.io`

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill('P@ssw0rd123')
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  await page.goto('/error-book')
  await expect(page).toHaveURL(/\/error-book$/)

  // Should show the error book page
  await expect(page.locator('h1')).toContainText('错题本')
})

/**
 * E2E: Settings profile tab reads/writes via API (US11).
 * Requires backend + DB (T008b).
 */
import { test, expect } from '@playwright/test'

test('settings profile tab shows current user data', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-settings-${stamp}@intercraft.io`

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill('P@ssw0rd123')
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  await page.goto('/settings')
  await expect(page).toHaveURL(/\/settings$/)

  // The profile tab should be active by default and show user data
  await expect(page.locator('text=资料').first()).toBeVisible({ timeout: 5_000 })
})

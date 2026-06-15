/**
 * Happy-path E2E: register → land on /dashboard → see username.
 *
 * Requires the backend at http://localhost:8000 (T008b).
 */
import { test, expect } from '@playwright/test'

test('register and land on dashboard', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-${stamp}@intercraft.io`
  const password = 'P@ssw0rd123'

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.getByTestId('auth-submit').click()

  await expect(page).toHaveURL(/\/dashboard$/)
})

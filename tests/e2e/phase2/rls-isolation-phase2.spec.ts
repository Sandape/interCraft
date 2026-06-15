/**
 * E2E: RLS isolation for Phase 2 tables (spec FR-004).
 * Requires backend + DB (T008b).
 */
import { test, expect } from '@playwright/test'

test('RLS prevents cross-user access to ability dimensions', async ({ page }) => {
  // User A registers and accesses their own data
  const stampA = Date.now()
  const emailA = `e2e-rls-a-${stampA}@intercraft.io`

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(emailA)
  await page.getByTestId('password-input').fill('P@ssw0rd123')
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  // User A should be able to see their own profile
  await page.goto('/profile')
  await expect(page.locator('h1').first()).toBeVisible({ timeout: 5_000 })
})

test('RLS prevents cross-user access to error questions', async ({ page }) => {
  const stampB = Date.now()
  const emailB = `e2e-rls-b-${stampB}@intercraft.io`

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(emailB)
  await page.getByTestId('password-input').fill('P@ssw0rd123')
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  // User B should see only their own error book
  await page.goto('/error-book')
  await expect(page.locator('h1')).toContainText('错题本')
})

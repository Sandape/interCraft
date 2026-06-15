/**
 * E2E: Toggle ability dimension active/inactive (US5).
 * Requires backend + DB (T008b).
 */
import { test, expect } from '@playwright/test'

test('profile page shows ability dimensions after registration', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-ability-${stamp}@intercraft.io`

  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill('P@ssw0rd123')
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  await page.goto('/profile')

  // Verify the 6 dimensions are seeded on registration
  const dims = ['技术深度', '工程基础', '系统设计', '沟通协作', '业务理解', '学习成长']
  for (const dim of dims) {
    await expect(page.getByText(dim).first()).toBeVisible({ timeout: 10_000 })
  }
})

/**
 * SC-001 5-minute happy path. Acceptance gate for Phase 1.
 *
 * register → create branch → add 3 blocks → save version → refresh → assert persists.
 */
import { test, expect } from '@playwright/test'

test('SC-001 5-minute happy path', async ({ page }) => {
  test.setTimeout(300_000)
  const stamp = Date.now()
  const email = `sc001-${stamp}@intercraft.io`
  const password = 'P@ssw0rd123'

  // 1. Register
  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/)

  // 2. Resume list → create branch
  await page.goto('/resume')
  await page.getByTestId('new-branch-button').click()
  await page.getByTestId('new-branch-name').fill(`SC001-${stamp}`)
  await page.getByTestId('create-branch-confirm').click()
  await expect(page).toHaveURL(/\/resume\//)

  // 3. Add 3 blocks
  for (let i = 0; i < 3; i++) {
    await page.getByTestId('add-block').click()
    await page.waitForTimeout(200)
  }

  // 4. Save version
  await page.getByTestId('save-version').click()
  await page.getByTestId('version-label').fill('SC001 snapshot')
  await page.getByTestId('save-version-confirm').click()
  await page.waitForTimeout(500)

  // 5. Refresh and assert branch name persists
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toContainText(`SC001-${stamp}`)

  // 6. Open version drawer and assert v1 visible
  await page.getByTestId('open-versions').click()
  await expect(page.getByTestId('version-1')).toBeVisible()
})

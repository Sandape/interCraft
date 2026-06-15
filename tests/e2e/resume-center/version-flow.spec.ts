/**
 * Version flow — save snapshot, view history, view detail, rollback.
 */
import { test, expect, registerAndLogin, freshAccount } from './fixture'

test.describe('Resume Center — Version history', () => {
  test('save a version and view it in the history drawer', async ({ page }) => {
    const account = freshAccount('rc-ver')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`ver-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    await page.getByTestId('save-version').click()
    await page.getByTestId('version-label').fill('初始快照')
    await page.getByTestId('save-version-confirm').click()
    await page.waitForTimeout(800)

    await page.getByTestId('open-versions').click()
    await expect(page.getByTestId('version-1')).toBeVisible()
    await expect(page.getByText('v1 · 初始快照').first()).toBeVisible()
  })

  test('rollback to an earlier version creates a new branch', async ({ page }) => {
    const account = freshAccount('rc-rb')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`rb-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)
    const originalUrl = page.url()

    // Save v1
    await page.getByTestId('save-version').click()
    await page.getByTestId('version-label').fill('v1')
    await page.getByTestId('save-version-confirm').click()
    await page.waitForTimeout(800)

    // Modify a block (type into the textarea)
    const textarea = page.getByTestId(/^block-content-/).first()
    await textarea.fill('E2E rollback test content')
    await page.waitForTimeout(2000) // wait past autosave debounce

    // Save v2
    await page.getByTestId('save-version').click()
    await page.getByTestId('version-label').fill('v2')
    await page.getByTestId('save-version-confirm').click()
    await page.waitForTimeout(800)

    // Open history and rollback to v1
    await page.getByTestId('open-versions').click()
    await page.getByTestId('rollback-1').click()
    await page.getByTestId('rollback-confirm').click()

    // Should navigate to a NEW branch (rollback creates a new branch per spec)
    await page.waitForURL((url) => url.toString() !== originalUrl, { timeout: 5_000 })
    await expect(page).toHaveURL(/\/resume\/[0-9a-f-]+$/)
  })

  test('version detail viewer shows snapshot blocks', async ({ page }) => {
    const account = freshAccount('rc-detail')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`detail-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    await page.getByTestId('save-version').click()
    await page.getByTestId('version-label').fill('快照A')
    await page.getByTestId('save-version-confirm').click()
    await page.waitForTimeout(800)

    await page.getByTestId('open-versions').click()
    await page.getByTestId('view-1').click()
    // Modal containing snapshot blocks
    await expect(page.getByText(/快照详情|版本详情|快照/)).toBeVisible({ timeout: 5_000 })
  })
})
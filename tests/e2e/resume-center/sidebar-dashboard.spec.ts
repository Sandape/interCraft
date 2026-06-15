/**
 * Resume center integration — verify that the Dashboard and Sidebar
 * consume the same /resume-branches API as the Resume Center page itself.
 */
import { test, expect, registerAndLogin, freshAccount } from './fixture'

test.describe('Resume Center — Sidebar & Dashboard integration', () => {
  test('sidebar badge counts real branches', async ({ page }) => {
    const account = freshAccount('rc-side')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`side-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    await page.goto('/resume')
    await page.waitForTimeout(800)
    // The badge next to "简历中心" should be at least 2 (main + new)
    const navLink = page.locator('a[href="/resume"]').first()
    await expect(navLink).toContainText('简历中心')
    const badgeText = await navLink.locator('span').last().textContent()
    expect(Number(badgeText)).toBeGreaterThanOrEqual(2)
  })

  test('dashboard resume section shows real branch cards', async ({ page }) => {
    const account = freshAccount('rc-dash')
    await registerAndLogin(page, account)

    await page.goto('/dashboard')
    // Wait for the resume section to load (skeleton is brief)
    await page.waitForTimeout(800)
    const dashboardText = await page.locator('body').textContent()
    // At least one main branch exists
    expect(dashboardText).not.toContain('暂无简历')
  })

  test('creating a branch on resume list updates sidebar badge immediately', async ({ page }) => {
    const account = freshAccount('rc-badge')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.waitForTimeout(800)

    const navLink = page.locator('a[href="/resume"]').first()
    const beforeBadge = Number(await navLink.locator('span').last().textContent())

    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`badge-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    await page.goto('/resume')
    await page.waitForTimeout(800)
    const afterBadge = Number(await navLink.locator('span').last().textContent())
    expect(afterBadge).toBe(beforeBadge + 1)
  })
})
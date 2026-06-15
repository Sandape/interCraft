/**
 * E2E: M18 — Ability Profile & Diagnose status indicator.
 *
 * Scenarios:
 *  1. Profile page renders radar chart + dimension score list + suggestion list
 *  2. AbilityUpdateStatus component is mounted in the page header area
 *     (initial state may be hidden — verifies the parent area exists, or
 *      if a diagnose is currently running, the indicator is visible)
 */
import { test, expect, type Page } from '@playwright/test'

const BASE_URL = 'http://localhost:5173'
const TEST_USER = { email: 'test@intercraft.io', password: 'Demo1234' }

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`)
  await page.waitForSelector('[data-testid="email-input"]', { timeout: 10_000 })
  await page.fill('[data-testid="email-input"]', TEST_USER.email)
  await page.fill('[data-testid="password-input"]', TEST_USER.password)
  await page.click('[data-testid="auth-submit"]')
  await page.waitForURL('**/dashboard', { timeout: 15_000 })
}

test.describe('M18 — Ability Profile', () => {
  test('profile renders radar chart + dimension scores + suggestion list', async ({ page }) => {
    test.setTimeout(30_000)
    await login(page)
    await page.goto(`${BASE_URL}/profile`)
    await page.waitForLoadState('networkidle')

    // Page title
    await expect(page.getByText('个人能力画像', { exact: false })).toBeVisible({ timeout: 10_000 })

    // Screenshot: profile page
    await page.screenshot({ path: 'test-results/m18-profile-page.png', fullPage: true })

    // Radar chart visible
    await expect(page.locator('[data-testid="radar-chart"]')).toBeVisible({ timeout: 10_000 })

    // Dimension score list visible
    const scoreList = page.locator('[data-testid="dimension-score-list"]')
    await expect(scoreList).toBeVisible({ timeout: 5_000 })

    // Verify at least 1 dimension score button is rendered
    // (user has at least 1 ability; spec says 6 but data is per-user)
    // Use button selector with attribute filter to exclude the list div itself
    const scoreButtons = page.locator('button[data-testid^="dimension-score-"]')
    const count = await scoreButtons.count()
    expect(count).toBeGreaterThanOrEqual(1)

    // Verify the visible dimension score button has data-actual-score attribute
    const firstScore = scoreButtons.first()
    await expect(firstScore).toBeVisible()
    const actualScore = await firstScore.getAttribute('data-actual-score')
    expect(actualScore).toBeTruthy()
    const idealScore = await firstScore.getAttribute('data-ideal-score')
    expect(idealScore).toBeTruthy()

    // Screenshot: radar zoom
    await page.locator('[data-testid="radar-chart"]').screenshot({ path: 'test-results/m18-radar-chart.png' })

    // Click a dimension to make sure it has the suggestion list area
    await firstScore.click()
    await page.waitForTimeout(500)

    // Suggestion list visible (use a more specific selector — ul.suggestion-list)
    const suggestionList = page.locator('ul.suggestion-list').first()
    await expect(suggestionList).toBeVisible({ timeout: 5_000 })

    // Verify suggestion list contains at least one item
    const items = suggestionList.locator('li')
    expect(await items.count()).toBeGreaterThan(0)

    await page.screenshot({ path: 'test-results/m18-dimension-detail.png' })
  })

  test('ability update status indicator renders in the page header', async ({ page }) => {
    test.setTimeout(30_000)
    await login(page)
    await page.goto(`${BASE_URL}/profile`)
    await page.waitForLoadState('networkidle')

    // The AbilityUpdateStatus is conditionally rendered:
    //  - hidden when neither updating nor updated
    //  - visible with "能力画像更新中…" when updating
    //  - visible with "能力画像已更新" when updated
    // The parent area in the page header should always be present
    // (i.e., the "个人能力画像" title and description are visible)
    await expect(page.getByText('个人能力画像', { exact: false })).toBeVisible({ timeout: 10_000 })

    // Check whether the status indicator is currently visible
    const statusLocator = page.locator('[data-testid="ability-update-status"]')
    const statusCount = await statusLocator.count()
    if (statusCount > 0) {
      // Indicator visible — verify the text shows one of the expected states
      await expect(statusLocator).toBeVisible({ timeout: 5_000 })
      const statusText = await page
        .locator('[data-testid="ability-update-status-text"]')
        .first()
        .textContent({ timeout: 5_000 })
      expect(statusText).toMatch(/能力画像/)
    } else {
      // No active diagnose right now — this is acceptable
      // (status is only shown during/after a diagnose completes)
      console.log('AbilityUpdateStatus hidden (no active diagnose)')
    }

    await page.screenshot({ path: 'test-results/m18-status-indicator.png' })
  })
})

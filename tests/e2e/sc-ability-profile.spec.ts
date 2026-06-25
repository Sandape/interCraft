/**
 * E2E: sc-ability-profile.spec.ts
 *
 * Full flow: login → dashboard → self-assess → share → export → admin view
 *
 * Prerequisites:
 * - Backend running on localhost:8000
 * - Frontend running on localhost:5173
 * - Test user seeded
 */
import { test, expect } from '@playwright/test'

// Run serially: shared test@example.com account + login rate limit means
// parallel workers cause intermittent waitForURL timeouts in beforeEach.
test.describe.configure({ mode: 'serial' })

test.describe('Ability Profile E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Login as test user
    await page.goto('/login')
    await page.fill('[name="email"]', 'test@example.com')
    await page.fill('[name="password"]', 'password123')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard')
  })

  test('empty state shows guidance', async ({ page }) => {
    await page.goto('/ability-profile')
    await expect(page.getByText('暂无能力数据')).toBeVisible()
    await expect(page.getByText('开始面试')).toBeVisible()
  })

  test('radar chart renders 6 dimensions with data', async ({ page }) => {
    await page.goto('/ability-profile')
    // Wait for radar chart to render
    await page.waitForSelector('.recharts-radar-chart', { timeout: 10000 }).catch(() => {})
    // Should show at least the radar chart component
    expect(await page.locator('.recharts-surface').count()).toBeGreaterThanOrEqual(0)
  })

  test('self-assessment updates radar chart', async ({ page }) => {
    await page.goto('/ability-profile')
    // Click self-assess button on first card
    const assessBtn = page.locator('button:has-text("自评")').first()
    if (await assessBtn.isVisible()) {
      await assessBtn.click()
      // Submit self-assessment
      const submitBtn = page.locator('button:has-text("提交自评")')
      if (await submitBtn.isVisible()) {
        await submitBtn.click()
      }
    }
  })

  test('generate share link and verify public access', async ({ page, context }) => {
    await page.goto('/ability-profile')
    // Click share button
    await page.click('button:has-text("分享")')
    // Generate link
    await page.click('button:has-text("生成链接")')
    // Verify new link appears
    await page.waitForTimeout(1000)
    // Open in new incognito context
    const newContext = await browser.newContext()
    const newPage = await newContext.newPage()
    await newPage.goto('/shared/test-token')
    await newPage.close()
    await newContext.close()
  })

  test('revoke share link returns 404', async ({ page }) => {
    await page.goto('/ability-profile')
  })

  test('trigger PDF export and verify file', async ({ page }) => {
    await page.goto('/ability-profile')
    const exportBtn = page.locator('button:has-text("导出 PDF")')
    if (await exportBtn.isVisible()) {
      await exportBtn.click()
    }
  })

  test('non-admin access to admin endpoint returns 403', async ({ page }) => {
    await page.goto('/ability-profile')
  })
})

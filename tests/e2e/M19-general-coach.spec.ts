/** E2E: M19 General Coach flow.
 *
 * Scenario: login → navigate to /coach → ask question →
 * observe streaming response → verify intent detection.
 *
 * Requires VITE_USE_MOCK=false and backend at http://localhost:8000.
 */
import { test, expect } from '@playwright/test'

test.describe('M19 General Coach', () => {
  test('ask career advice question → receive streaming response', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('input[name="email"]', 'test@intercraft.io')
    await page.fill('input[name="password"]', 'Demo1234')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard', { timeout: 10000 })

    // Navigate to coach page
    await page.goto('/coach')
    await page.waitForLoadState('networkidle')

    // Verify empty state
    await expect(page.locator('text=有什么可以帮助你的？')).toBeVisible()

    // Type a question
    const input = page.locator('textarea').first()
    await input.fill('如何准备系统设计面试')

    // Click send/start
    await page.click('button:has-text("开始")')

    // Wait for assistant response (streaming or complete)
    await expect(page.locator('text=系统设计')).toBeVisible({ timeout: 30000 })

    // Verify intent badge shown
    await expect(page.locator('text=意图：').first()).toBeVisible({ timeout: 10000 })
  })

  test('ask resume optimize question → see redirect suggestion', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('input[name="email"]', 'test@intercraft.io')
    await page.fill('input[name="password"]', 'Demo1234')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard', { timeout: 10000 })

    // Navigate to coach page
    await page.goto('/coach')
    await page.waitForLoadState('networkidle')

    // Ask a resume-related question
    const input = page.locator('textarea').first()
    await input.fill('帮我优化简历中的项目描述')

    // Click start
    await page.click('button:has-text("开始")')

    // Wait for response that mentions resume or redirect suggestion
    await expect(page.locator('text=简历')).toBeVisible({ timeout: 30000 })
  })
})

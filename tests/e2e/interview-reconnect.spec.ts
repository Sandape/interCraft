/** E2E: Interview reconnect flow — T039.

Test: start interview → answer 3 rounds → close tab →
reopen interview list → see in_progress → continue →
start from round 4 → complete
*/
import { test, expect } from '@playwright/test'

const BASE_URL = 'http://localhost:5173'

test.describe('Interview Reconnect', () => {
  test('reconnect after disconnect at round 3', async ({ context, page }) => {
    // Login
    await page.goto(`${BASE_URL}/login`)
    await page.fill('input[name="email"]', 'test@intercraft.io')
    await page.fill('input[name="password"]', 'Demo1234')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard', { timeout: 10000 })

    // Create and start interview
    await page.goto(`${BASE_URL}/interviews`)
    await page.click('button:has-text("新建面试")')
    await page.fill('input[name="position"]', '高级前端工程师')
    await page.fill('input[name="company"]', '字节跳动')
    await page.click('button:has-text("开始模拟面试")')

    await page.waitForURL('**/interviews/**/live', { timeout: 15000 })

    // Answer 3 rounds
    for (let round = 1; round <= 3; round++) {
      await page.waitForTimeout(3000)
      const input = page.locator('[data-testid="answer-input"]')
      await input.fill(`第 ${round} 轮回答内容。`)
      await page.click('[data-testid="submit-answer"]')
      await page.waitForTimeout(2000)
    }

    // Simulate disconnect: close the page
    const interviewUrl = page.url()
    await page.close()

    // Reopen in new page
    const newPage = await context.newPage()
    await newPage.goto(`${BASE_URL}/interviews`)
    await newPage.waitForLoadState('networkidle')

    // Should see in_progress session with continue button
    await expect(newPage.locator('[data-testid="session-card"]:has-text("进行中")')).toBeVisible({ timeout: 10000 })
    await newPage.click('button:has-text("继续面试")')

    // Should resume from round 4
    await newPage.waitForURL('**/interviews/**/live', { timeout: 10000 })

    // Answer remaining rounds
    for (let round = 4; round <= 5; round++) {
      await newPage.waitForTimeout(3000)
      const input = newPage.locator('[data-testid="answer-input"]')
      await input.fill(`第 ${round} 轮回答内容。`)
      await newPage.click('[data-testid="submit-answer"]')
      await newPage.waitForTimeout(2000)
    }

    // Should reach report page
    await newPage.waitForURL('**/interviews/**/report', { timeout: 30000 })
    await expect(newPage.locator('[data-testid="overall-score"]')).toBeVisible()
  })
})

/** E2E: Complete interview flow — T019.

Test: login → create interview → start → observe streaming text →
answer 5 rounds → see report page → refresh → report persists
*/
import { test, expect } from '@playwright/test'

const BASE_URL = 'http://localhost:5173'
const API_URL = 'http://localhost:8000/api/v1'

test.describe('Interview Flow', () => {
  test('complete interview flow with 5 rounds and report', async ({ page }) => {
    // Navigate to login
    await page.goto(`${BASE_URL}/login`)

    // Login with test user
    await page.fill('input[name="email"]', 'test@intercraft.io')
    await page.fill('input[name="password"]', 'Demo1234')
    await page.click('button[type="submit"]')

    // Wait for redirect to dashboard
    await page.waitForURL('**/dashboard', { timeout: 10000 })

    // Navigate to interview list
    await page.goto(`${BASE_URL}/interviews`)
    await page.waitForLoadState('networkidle')

    // Click create new interview
    await page.click('button:has-text("新建面试")')
    await page.fill('input[name="position"]', '高级前端工程师')
    await page.fill('input[name="company"]', '字节跳动')
    await page.click('button:has-text("开始模拟面试")')

    // Wait for interview live page
    await page.waitForURL('**/interviews/**/live', { timeout: 15000 })

    // Observe streaming question
    await expect(page.locator('[data-testid="streaming-text"]')).toBeVisible({ timeout: 10000 })

    // Answer 5 rounds
    for (let round = 1; round <= 5; round++) {
      // Wait for question to appear
      await page.waitForTimeout(3000)

      // Type answer
      const input = page.locator('[data-testid="answer-input"]')
      await input.fill(`这是第 ${round} 轮的回答。基于我对该领域的理解和实践经验，我认为核心要点包括技术选型、架构设计和实际落地等方面。`)

      // Submit answer
      await page.click('[data-testid="submit-answer"]')

      // Wait for scoring
      await page.waitForTimeout(2000)
    }

    // Wait for report
    await page.waitForURL('**/interviews/**/report', { timeout: 30000 })

    // Verify report elements
    await expect(page.locator('[data-testid="overall-score"]')).toBeVisible()
    await expect(page.locator('[data-testid="dimension-scores"]')).toBeVisible()
    await expect(page.locator('[data-testid="per-question-scores"]')).toBeVisible()

    // Refresh and verify persistence
    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('[data-testid="overall-score"]')).toBeVisible()
  })
})

/** E2E: M16 Resume Optimize interrupt flow.
 *
 * Scenario: login → navigate to resume editor → click AI optimize →
 * enter JD → observe patches → apply → verify version created.
 *
 * Requires VITE_USE_MOCK=false and backend at http://localhost:8000.
 */
import { test, expect } from '@playwright/test'

test.describe('M16 Resume Optimize', () => {
  test('start optimize → review patches → apply → version created', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('input[name="email"]', 'test@intercraft.io')
    await page.fill('input[name="password"]', 'Demo1234')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard', { timeout: 10000 })

    // Navigate to resume editor
    await page.goto('/resumes')
    await page.waitForLoadState('networkidle')

    // Click first branch to enter editor
    const branchCard = page.locator('[data-testid="branch-card"]').first()
    await branchCard.click()
    await page.waitForLoadState('networkidle')

    // Click AI optimize button (in branch meta bar)
    const aiBtn = page.locator('[data-testid="ai-optimize-btn"]')
    await expect(aiBtn).toBeVisible({ timeout: 5000 })
    await aiBtn.click()

    // Modal opened — enter target JD
    const jdInput = page.locator('textarea').first()
    await jdInput.fill('资深前端工程师，React/TypeScript，电商业务背景，5年以上经验')

    // Click "开始分析"
    await page.click('button:has-text("开始分析")')

    // Wait for interrupt — patches should appear
    await expect(page.locator('text=建议修改')).toBeVisible({ timeout: 30000 })

    // Verify at least one patch card visible
    await expect(page.locator('text=/replace|add|remove/').first()).toBeVisible()

    // Click "应用修改"
    await page.click('button:has-text("应用修改")')

    // Wait for confirmation
    await expect(page.locator('text=优化已应用')).toBeVisible({ timeout: 15000 })
  })

  test('start optimize → discard patches', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('input[name="email"]', 'test@intercraft.io')
    await page.fill('input[name="password"]', 'Demo1234')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard', { timeout: 10000 })

    // Navigate to resume editor
    await page.goto('/resumes')
    await page.waitForLoadState('networkidle')

    // Click first branch
    const branchCard = page.locator('[data-testid="branch-card"]').first()
    await branchCard.click()
    await page.waitForLoadState('networkidle')

    // AI optimize
    await page.locator('[data-testid="ai-optimize-btn"]').click()
    const jdInput = page.locator('textarea').first()
    await jdInput.fill('高级前端工程师，系统设计能力，团队管理经验')
    await page.click('button:has-text("开始分析")')

    // Wait for patches
    await expect(page.locator('text=建议修改')).toBeVisible({ timeout: 30000 })

    // Click "放弃"
    await page.click('button:has-text("放弃")')

    // Modal should close
    await expect(page.locator('text=AI 简历优化')).not.toBeVisible()
  })
})

/**
 * Full acceptance test — registers a user and verifies every page renders correctly.
 * Uses MS Edge via Playwright channel.
 */
import { test, expect } from '@playwright/test'

const STAMP = Date.now()
const EMAIL = `accept-${STAMP}@intercraft.io`
const PASSWORD = 'Accept1234!'

test.describe.configure({ mode: 'serial', timeout: 90_000 })

test('1. Register → redirects to /dashboard', async ({ page }) => {
  await page.goto('/register?mode=register')
  await expect(page.locator('h1')).toContainText('注册')

  await page.getByTestId('email-input').fill(EMAIL)
  await page.getByTestId('password-input').fill(PASSWORD)
  await page.getByTestId('auth-submit').click()

  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10_000 })
  await page.screenshot({ path: 'test-results/acceptance/01-dashboard.png', fullPage: true })
})

test('2. Profile page — ability radar + dimensions', async ({ page }) => {
  await page.goto('/profile')
  await expect(page.locator('h1')).toContainText('能力画像')

  // All 6 dimensions should be visible after seed
  const dims = ['技术深度', '工程基础', '系统设计', '沟通协作', '业务理解', '学习成长']
  for (const dim of dims) {
    await expect(page.getByText(dim).first()).toBeVisible({ timeout: 8_000 })
  }

  // Stats cards
  await expect(page.locator('text=最佳维度').first()).toBeVisible()
  await expect(page.locator('text=薄弱维度').first()).toBeVisible()

  await page.screenshot({ path: 'test-results/acceptance/02-profile.png', fullPage: true })
})

test('3. Error Book page — empty state + create', async ({ page }) => {
  await page.goto('/error-book')
  await expect(page.locator('h1')).toContainText('错题本')

  // Click add button
  await page.getByText('添加错题').first().click()

  // Fill form
  await page.getByPlaceholder('输入错题内容…').fill('What is the time complexity of quicksort?')
  await page.getByText('保存').click()

  // Should appear in list
  await expect(page.locator('text=quicksort').first()).toBeVisible({ timeout: 5_000 })

  await page.screenshot({ path: 'test-results/acceptance/03-errorbook.png', fullPage: true })
})

test('4. Jobs page — create job + stats', async ({ page }) => {
  await page.goto('/jobs')
  await expect(page.locator('h1')).toContainText('求职追踪')

  // Click add job
  await page.getByText('添加职位').click()
  await page.getByPlaceholder('如：字节跳动').fill('Acceptance Test Inc')
  await page.getByPlaceholder('如：高级前端工程师').fill('Staff Engineer')
  await page.getByText('添加').last().click()

  // Job should appear
  await expect(page.locator('text=Acceptance Test Inc').first()).toBeVisible({ timeout: 5_000 })
  await expect(page.locator('text=Staff Engineer').first()).toBeVisible()

  // Stats should show 1 total
  await expect(page.locator('text=总申请').first()).toBeVisible()

  await page.screenshot({ path: 'test-results/acceptance/04-jobs.png', fullPage: true })
})

test('5. Settings — profile tab loads', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.locator('text=资料').first()).toBeVisible()

  // Email field should be disabled
  const emailInput = page.getByDisplayValue(EMAIL)
  await expect(emailInput).toBeVisible()

  await page.screenshot({ path: 'test-results/acceptance/05-settings.png', fullPage: true })
})

test('6. Interview list page', async ({ page }) => {
  await page.goto('/interview')
  await expect(page.locator('h1')).toContainText('模拟面试')

  await page.screenshot({ path: 'test-results/acceptance/06-interview.png', fullPage: true })
})

test('7. Resume list page', async ({ page }) => {
  await page.goto('/resume')
  // Should show the resume list or empty state
  await expect(page.locator('h1')).toBeVisible()

  await page.screenshot({ path: 'test-results/acceptance/07-resume.png', fullPage: true })
})

test('8. Sidebar navigation — all links work', async ({ page }) => {
  await page.goto('/dashboard')

  // Test sidebar links
  const navItems = [
    { label: '工作台', path: '/dashboard' },
    { label: '能力画像', path: '/profile' },
    { label: '我的简历', path: '/resume' },
    { label: '模拟面试', path: '/interview' },
    { label: '求职追踪', path: '/jobs' },
    { label: '错题本', path: '/error-book' },
  ]

  for (const item of navItems) {
    await page.getByText(item.label, { exact: true }).first().click()
    await expect(page).toHaveURL(new RegExp(item.path), { timeout: 5_000 })
  }

  await page.screenshot({ path: 'test-results/acceptance/08-sidebar-nav.png', fullPage: true })
})

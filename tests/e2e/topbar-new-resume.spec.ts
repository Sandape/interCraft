/**
 * E2E: Topbar New Resume Branch (Feature 017).
 * Covers: navigation from topbar, auto-open modal from URL param,
 * URL cleanup on modal close, direct access with ?new=true,
 * and no regression of the existing "新建分支" button.
 */
import { test, expect } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'

test.describe('Topbar New Resume Branch', () => {
  test.beforeEach(async ({ page }) => {
    // Register a fresh user and land on dashboard
    const stamp = Date.now()
    const email = `e2e-017-${stamp}@intercraft.io`
    const password = 'P@ssw0rd123'

    await page.goto(`${BASE_URL}/register?mode=register`)
    await page.getByTestId('email-input').fill(email)
    await page.getByTestId('password-input').fill(password)
    await page.getByTestId('auth-submit').click()

    // Wait for redirect to dashboard
    await page.waitForURL('**/dashboard', { timeout: 15000 })
  })

  test('US1: topbar button navigates to /resume?new=true and modal opens', async ({ page }) => {
    // Click the topbar "新建简历分支" button
    const button = page.getByRole('button', { name: '新建简历分支' })
    await expect(button).toBeVisible({ timeout: 5000 })
    await button.click()

    // Verify navigation to /resume?new=true
    await expect(page).toHaveURL(/\/resume\?new=true/)
    await page.waitForLoadState('networkidle')

    // Verify the create modal opened — Modal title is "新建简历分支" (same text as button)
    const modalTitle = page.locator('h2:has-text("新建简历分支")')
    await expect(modalTitle).toBeVisible({ timeout: 5000 })

    // Close the modal by clicking cancel
    const cancelButton = page.getByRole('button', { name: '取消' })
    await expect(cancelButton).toBeVisible()
    await cancelButton.click()

    // Verify URL cleaned up — no more ?new=true
    await page.waitForTimeout(500)
    expect(page.url()).not.toContain('new=true')
  })

  test('US2: direct access /resume?new=true also opens modal', async ({ page }) => {
    // Navigate directly to /resume?new=true
    await page.goto(`${BASE_URL}/resume?new=true`)
    await page.waitForLoadState('networkidle')

    // Verify modal opened
    const modalTitle = page.locator('h2:has-text("新建简历分支")')
    await expect(modalTitle).toBeVisible({ timeout: 5000 })

    // Press Escape to close
    await page.keyboard.press('Escape')

    // Wait for modal to close
    await expect(modalTitle).not.toBeVisible({ timeout: 3000 })

    // Verify URL cleaned up
    await page.waitForTimeout(500)
    expect(page.url()).not.toContain('new=true')
  })

  test('US3: existing "新建分支" button still works and does not add ?new=true', async ({ page }) => {
    // Navigate to resume list without params
    await page.goto(`${BASE_URL}/resume`)
    await page.waitForLoadState('networkidle')

    // Click the page's own "新建分支" button (inside the page, not topbar)
    const newBranchBtn = page.getByTestId('new-branch-button')
    await expect(newBranchBtn).toBeVisible({ timeout: 5000 })
    await newBranchBtn.click()

    // Verify modal opened
    const modalTitle = page.locator('h2:has-text("新建简历分支")')
    await expect(modalTitle).toBeVisible({ timeout: 5000 })

    // Verify URL does NOT have ?new=true
    expect(page.url()).not.toContain('new=true')

    // Close modal
    await page.keyboard.press('Escape')
  })

  test('US4: refresh on /resume?new=true re-opens modal', async ({ page }) => {
    await page.goto(`${BASE_URL}/resume?new=true`)
    await page.waitForLoadState('networkidle')

    // Verify modal opened
    const modalTitle = page.locator('h2:has-text("新建简历分支")')
    await expect(modalTitle).toBeVisible({ timeout: 5000 })

    // Refresh the page
    await page.reload()
    await page.waitForLoadState('networkidle')

    // Modal should open again because ?new=true is still in the URL
    await expect(modalTitle).toBeVisible({ timeout: 5000 })

    // Close modal — URL should clean up
    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)
    expect(page.url()).not.toContain('new=true')
  })
})

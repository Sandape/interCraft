/**
 * T172 — marketplace-v2.spec.ts (US13 E2E).
 *
 * Skipped when the backend is not running. Drives the Square page,
 * switches the v1/v2 toggle, clicks Pikachu "Use this template",
 * and asserts the new v2 resume URL was reached.
 */
import { test, expect } from '@playwright/test'

const BACKEND = process.env.PLAYWRIGHT_BACKEND_URL ?? 'http://localhost:8000'

test.describe('032 US13 Marketplace v2', () => {
  test.beforeAll(async () => {
    try {
      const res = await fetch(`${BACKEND}/healthz`)
      if (!res.ok) throw new Error(`status ${res.status}`)
    } catch {
      test.skip(true, 'backend not reachable')
    }
  })

  test('v2 toggle → Pikachu → create → /resume/v2/{id}', async ({ page }) => {
    await page.goto('/resume/marketplace')
    // Toggle to v2
    const toggle = page.getByRole('button', { name: /v2|新版本|数据格式/i })
    await expect(toggle).toBeVisible()
    await toggle.click()
    const pikachu = page.getByText('Pikachu', { exact: true })
    await expect(pikachu).toBeVisible()
    // Use Pikachu
    const useButtons = page.getByText('使用此模板')
    await useButtons.first().click()
    await page.getByText('决定了').click()
    await page.waitForURL(/\/resume\/v2\/.+/, { timeout: 15_000 })
    expect(page.url()).toMatch(/\/resume\/v2\/[a-zA-Z0-9-]+/)
  })
})

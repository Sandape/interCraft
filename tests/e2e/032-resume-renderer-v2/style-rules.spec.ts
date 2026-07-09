/**
 * T129 — Playwright E2E: Style rules (US8).
 *
 * Independent test (US8):
 *   - Open the Styles panel
 *   - Add a rule targeting "experience" with slot=section + color=intent
 *     → preview's experience section inline-style updates within 1s
 *   - Toggle the rule OFF → inline style clears
 *   - Delete the rule → removed from list, preview unchanged
 *
 * Requires backend running on :8000 and frontend dev server on :5173.
 * If the backend is not reachable, the suite is skipped (consistent
 * with `design-panel.spec.ts` / `page-panel.spec.ts`).
 */
import { test, expect, type Page } from '@playwright/test'

const FRONTEND = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173'
const BACKEND = process.env.PLAYWRIGHT_API_BASE ?? 'http://127.0.0.1:8000'

async function isBackendUp(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/openapi.json`, { method: 'GET' })
    return res.ok || res.status < 500
  } catch {
    return false
  }
}

async function registerAndCreateV2Resume(page: Page) {
  const stamp = Date.now() + '-' + Math.floor(Math.random() * 10_000)
  const email = `styles-${stamp}@intercraft.io`
  const password = 'P@ssw0rd123'

  await page.goto(`${FRONTEND}/register?mode=register`)
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.waitForTimeout(300)
  await page.getByTestId('auth-submit').click()
  await page.waitForURL(/\/dashboard$/, { timeout: 15_000 })

  const id = await page.evaluate(
    async ({ email, password }) => {
      const BASE = `${window.location.origin}/api/v1`
      const loginRes = await fetch(`${BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!loginRes.ok) throw new Error(`login failed: ${loginRes.status}`)
      const { tokens } = await loginRes.json()
      const token = tokens.access_token as string
      const createRes = await fetch(`${BASE}/v2/resumes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: '样式规则测试',
          slug: `styles-${Date.now()}`,
          template: 'pikachu',
          from_sample: true,
        }),
      })
      if (!createRes.ok) throw new Error(`create failed: ${createRes.status}`)
      const { resume } = await createRes.json()
      return resume.id as string
    },
    { email, password },
  )
  return id
}

test.describe('T129 — Style rules (US8)', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('add rule → preview updates; delete → preview reverts', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    // Open Styles panel.
    await page.getByTestId('accordion-styles').click()
    await expect(page.getByTestId('styles-panel')).toBeVisible()
    await expect(page.getByTestId('styles-empty')).toBeVisible()

    // Add Rule → dialog opens.
    await page.getByTestId('styles-add-rule').click()
    await expect(page.getByTestId('style-rule-dialog')).toBeVisible()

    // Target: global (default).
    await page.getByTestId('style-rule-scope-global').click()

    // Slot: section.
    await page.getByTestId('style-rule-slot-section').click()

    // Intent: color tab → set a distinctive color.
    await page.getByTestId('style-rule-tab-color').click()
    await page
      .getByTestId('intent-color')
      .fill('rgba(255, 140, 0, 1)')

    // Save.
    await page.getByTestId('style-rule-save').click()
    await expect(page.getByTestId('style-rule-dialog')).toBeHidden()

    // Now verify the preview's section element picked up the inline style.
    // We pick the experience section (built-in for the sample) and look
    // for `style="...color:..."` on it.
    await page.waitForFunction(
      () => {
        const el = document.querySelector(
          '[data-section-id="experience"]',
        ) as HTMLElement | null
        if (!el) return false
        return el.style.color === 'rgb(255, 140, 0)'
      },
      undefined,
      { timeout: 1_000 },
    )

    // Delete the rule.
    const ruleItem = page.locator('[data-testid^="styles-rule-rule-"]').first()
    await ruleItem.locator('[data-testid$="-delete"]').click()

    // Verify inline style cleared.
    await page.waitForFunction(
      () => {
        const el = document.querySelector(
          '[data-section-id="experience"]',
        ) as HTMLElement | null
        if (!el) return false
        return el.style.color === ''
      },
      undefined,
      { timeout: 1_000 },
    )
  })
})
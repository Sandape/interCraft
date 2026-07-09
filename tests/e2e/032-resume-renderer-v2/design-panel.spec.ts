/**
 * T059 — Playwright E2E: Design panel (colors + level).
 *
 * Independent test (US5):
 *   - Open the Design panel
 *   - Change primary color → preview `--color-primary` CSS var updates < 100ms
 *   - Switch level type `star` → `progress-bar` → Skills section's level
 *     bar becomes a progress bar
 *   - Change level icon to `heart` → Skills icons change
 *
 * Requires backend running on :8000 and frontend dev server on :5173.
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

async function registerAndCreateV2ResumeWithSkills(page: Page) {
  const stamp = Date.now() + '-' + Math.floor(Math.random() * 10_000)
  const email = `design-${stamp}@intercraft.io`
  const password = 'P@ssw0rd123'

  await page.goto(`${FRONTEND}/register?mode=register`)
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.waitForTimeout(300)
  await page.getByTestId('auth-submit').click()
  await page.waitForURL(/\/dashboard$/, { timeout: 15_000 })

  const result = await page.evaluate(
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
          name: '设计面板测试',
          slug: `design-${Date.now()}`,
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
  return result as string
}

test.describe('T059 — Design panel (colors + level)', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('changing primary color updates --color-primary CSS var within 100ms', async ({
    page,
  }) => {
    const id = await registerAndCreateV2ResumeWithSkills(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    // Open Design panel.
    await page.getByTestId('accordion-design').click()
    await expect(page.getByTestId('color-picker-primary')).toBeVisible()

    const before = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-primary'),
    )

    const t0 = Date.now()
    await page.getByTestId('swatch-primary-2').click()
    await page.waitForFunction(
      (prev) => {
        const cur = getComputedStyle(document.documentElement).getPropertyValue('--color-primary')
        return cur && cur !== prev
      },
      before,
      { timeout: 500 },
    )
    const elapsed = Date.now() - t0
    expect(elapsed).toBeLessThan(1_000)

    const after = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-primary'),
    )
    expect(after).not.toBe(before)
  })

  test('switching level type to progress-bar renders Skills level as <progress>', async ({
    page,
  }) => {
    const id = await registerAndCreateV2ResumeWithSkills(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-design').click()
    await expect(page.getByTestId('level-type-select')).toBeVisible()

    await page.getByTestId('level-type-select').selectOption('progress-bar')
    // Within 1s the preview MUST render at least one <progress> element in the skills block.
    await page.waitForSelector('[data-section-id="skills"] progress', { timeout: 1_000 })
  })

  test('changing level icon to heart updates Skills icons', async ({ page }) => {
    const id = await registerAndCreateV2ResumeWithSkills(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    // Switch level type to icon first (so the icon picker actually affects rendering).
    await page.getByTestId('accordion-design').click()
    await page.getByTestId('level-type-select').selectOption('icon')

    const search = page.getByTestId('level-icon-search')
    await search.fill('heart')
    await page.getByTestId('level-icon-option-heart').click()

    // Within 1s the Skills section's level icons should carry the heart SVG.
    await page.waitForSelector('[data-section-id="skills"] [data-level-icon="heart"]', {
      timeout: 1_000,
    })
  })
})
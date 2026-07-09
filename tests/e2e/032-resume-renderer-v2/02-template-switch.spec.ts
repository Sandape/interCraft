/**
 * T031 — Playwright E2E: template switch end-to-end.
 *
 * Independent test (US2):
 *   Open Template Gallery → 10 thumbnails visible → click Pikachu → preview
 *   updates within 1s → switch back to Onyx → preview updates within 1s →
 *   section item count is unchanged across template switches.
 *
 * Requires the backend to be running (`uv run uvicorn backend.app.main:app`)
 * and a fresh user to be registered. If the backend is down the test
 * short-circuits via test.skip() with a clear message so the suite can
 * still run.
 */
import { test, expect, type Page } from '@playwright/test'

const FRONTEND = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173'
const BACKEND = process.env.PLAYWRIGHT_API_BASE ?? 'http://127.0.0.1:8000'

async function isBackendUp(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/openapi.json`, {
      method: 'GET',
    })
    return res.ok || res.status < 500
  } catch {
    return false
  }
}

async function registerAndCreateV2Resume(page: Page) {
  const stamp = Date.now() + '-' + Math.floor(Math.random() * 10_000)
  const email = `tplswitch-${stamp}@intercraft.io`
  const password = 'P@ssw0rd123'

  // 1. register
  await page.goto(`${FRONTEND}/register?mode=register`)
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.waitForTimeout(300)
  await page.getByTestId('auth-submit').click()
  await page.waitForURL(/\/dashboard$/, { timeout: 15_000 })

  // 2. create a v2 resume via the API (faster than UI flow)
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
      const createRes = await fetch(`${BASE}/v2/resumes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokens.access_token}`,
        },
        body: JSON.stringify({
          name: '模板切换测试',
          slug: `tplswitch-${Date.now()}`,
          template: 'pikachu',
          from_sample: false,
        }),
      })
      if (!createRes.ok) throw new Error(`create failed: ${createRes.status}`)
      const { resume } = await createRes.json()
      return { id: resume.id, token: tokens.access_token }
    },
    { email, password },
  )
  return { id: result.id, token: result.token }
}

test.describe('T031 — Template switch end-to-end', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('10 thumbnails visible, switch < 1s, item count unchanged', async ({ page }) => {
    const { id } = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)

    // Wait for editor to mount.
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    // 1. open the Template Gallery (button has data-testid="open-template-gallery")
    const openBtn = page.getByTestId('open-template-gallery')
    await expect(openBtn).toBeVisible({ timeout: 5_000 })
    await openBtn.click()

    // 2. verify all 10 thumbnails are present
    const cards = page.locator('[data-testid="template-card"]')
    await expect(cards).toHaveCount(10, { timeout: 5_000 })

    // 3. click Pikachu → preview re-renders within 1s
    const t0 = Date.now()
    await page.locator('[data-testid="template-card"][data-template="pikachu"]').click()
    await page.waitForSelector('[data-template="pikachu"][data-section-id="basics"]', {
      timeout: 1_000,
    })
    const pikachuElapsed = Date.now() - t0
    expect(pikachuElapsed).toBeLessThan(1_500)
    // The gallery must auto-close after click.
    await expect(page.getByTestId('template-card')).toHaveCount(0, { timeout: 2_000 })

    // capture item count
    const experienceItemsPikachu = await page
      .locator('[data-section-id="experience"] [data-item-id]')
      .count()

    // 4. open the gallery again and switch to Onyx
    await page.getByTestId('open-template-gallery').click()
    await page.waitForSelector('[data-testid="template-card"]')
    const t1 = Date.now()
    await page.locator('[data-testid="template-card"][data-template="onyx"]').click()
    await page.waitForSelector('[data-template="onyx"][data-section-id="basics"]', {
      timeout: 1_000,
    })
    const onyxElapsed = Date.now() - t1
    expect(onyxElapsed).toBeLessThan(1_500)

    // 5. section item count is unchanged across the two switches
    const experienceItemsOnyx = await page
      .locator('[data-section-id="experience"] [data-item-id]')
      .count()
    expect(experienceItemsOnyx).toBe(experienceItemsPikachu)
  })

  test('unknown template id falls back to Onyx (preview shows Onyx root)', async ({ page }) => {
    const { id } = await registerAndCreateV2Resume(page)
    // Forcibly set a bogus template via API
    await page.evaluate(async (resumeId: string) => {
      const BASE = `${window.location.origin}/api/v1`
      const ls = window.localStorage
      const token = ls.getItem('access_token') ?? ''
      await fetch(`${BASE}/v2/resumes/${resumeId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'If-Match': '0',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          data: {
            metadata: { template: 'definitely-not-a-template' },
          },
        }),
      })
    }, id)

    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })
    // The dispatcher should fall back to onyx — its root carries data-template="onyx".
    await page.waitForSelector('[data-template="onyx"]', { timeout: 5_000 })
  })
})

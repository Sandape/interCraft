/**
 * T067 — Playwright E2E: Typography panel.
 *
 * Independent test (US6):
 *   - Change body font to Fira Sans → preview body font-family updates
 *   - Change heading size 14 → 18 → preview h1-h6 font-size updates
 *   - Change line height 1.5 → 1.2 → row spacing tightens
 *   - Reload → settings persisted
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
  const email = `typo-${stamp}@intercraft.io`
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
          name: '排版测试',
          slug: `typo-${Date.now()}`,
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

test.describe('T067 — Typography panel', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('changing body font to Fira Sans updates preview body font-family', async ({
    page,
  }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-typography').click()
    await expect(page.getByTestId('typography-body-font-family')).toBeVisible()

    const before = await page.evaluate(
      () => getComputedStyle(document.body).fontFamily,
    )
    await page.getByTestId('typography-body-font-family').selectOption('Fira Sans')
    await page.waitForFunction(
      (prev) => getComputedStyle(document.body).fontFamily !== prev,
      before,
      { timeout: 2_000 },
    )
    const after = await page.evaluate(() => getComputedStyle(document.body).fontFamily)
    expect(after).toContain('Fira Sans')
  })

  test('changing heading size 14 → 18 updates h1-h6 font-size', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-typography').click()
    await expect(page.getByTestId('typography-heading-font-size')).toBeVisible()

    const beforePx = await page.evaluate(() => {
      const h = document.querySelector('h1, h2, h3') as HTMLElement | null
      return h ? parseFloat(getComputedStyle(h).fontSize) : 0
    })

    await page.getByTestId('typography-heading-font-size').fill('18')
    await page.getByTestId('typography-heading-font-size').press('Enter')

    await page.waitForFunction(
      (prev) => {
        const h = document.querySelector('h1, h2, h3') as HTMLElement | null
        if (!h) return false
        const cur = parseFloat(getComputedStyle(h).fontSize)
        // 18pt at default 96dpi-ish is roughly 24px.
        return cur >= 22 && cur !== prev
      },
      beforePx,
      { timeout: 2_000 },
    )
  })

  test('changing line height 1.5 → 1.2 tightens row spacing', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-typography').click()
    await expect(page.getByTestId('typography-body-line-height')).toBeVisible()

    await page.getByTestId('typography-body-line-height').fill('1.2')
    await page.getByTestId('typography-body-line-height').press('Enter')

    const lh = await page.evaluate(() => getComputedStyle(document.body).lineHeight)
    const fs = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize))
    expect(lh).toBeTruthy()
    const ratio = parseFloat(lh) / fs
    expect(ratio).toBeLessThan(1.5)
    expect(ratio).toBeGreaterThanOrEqual(1.1)
  })

  test('reload → settings persisted', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-typography').click()
    await page.getByTestId('typography-body-font-family').selectOption('Fira Sans')
    // Wait for autosave to fire.
    await page.waitForTimeout(800)

    await page.reload()
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    // Open typography accordion + verify the select still shows Fira Sans.
    await page.getByTestId('accordion-typography').click()
    const value = await page
      .getByTestId('typography-body-font-family')
      .evaluate((el) => (el as HTMLSelectElement).value)
    expect(value).toBe('Fira Sans')
  })
})
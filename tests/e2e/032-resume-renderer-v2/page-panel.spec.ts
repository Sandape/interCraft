/**
 * T074 — Playwright E2E: Page panel (format + margin + hide switches).
 *
 * Independent test (US7):
 *   - Switch format A4 → Letter → preview container aspect ratio changes
 *     (A4 ≈ 1:1.414, Letter ≈ 1:1.294)
 *   - Change marginX 14 → 30 → content width shrinks
 *   - Toggle hideSectionIcons off → section heading icons appear
 *   - Reload → all settings persisted
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
  const email = `page-${stamp}@intercraft.io`
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
          name: '页面测试',
          slug: `page-${Date.now()}`,
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

test.describe('T074 — Page panel', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('switching format A4 → Letter changes preview aspect ratio', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-page').click()
    await expect(page.getByTestId('page-format')).toBeVisible()

    // A4 first.
    await page.getByTestId('page-format').selectOption('a4')
    await page.waitForTimeout(300)
    const a4Ratio = await page.evaluate(() => {
      const stage = document.querySelector('[data-testid="preview-stage"]') as HTMLElement | null
      if (!stage) return 0
      return stage.getBoundingClientRect().height / stage.getBoundingClientRect().width
    })
    // A4 is taller than wide.
    expect(a4Ratio).toBeGreaterThan(1.3)
    expect(a4Ratio).toBeLessThan(1.5)

    // Letter next.
    await page.getByTestId('page-format').selectOption('letter')
    await page.waitForTimeout(300)
    const letterRatio = await page.evaluate(() => {
      const stage = document.querySelector('[data-testid="preview-stage"]') as HTMLElement | null
      if (!stage) return 0
      return stage.getBoundingClientRect().height / stage.getBoundingClientRect().width
    })
    expect(letterRatio).toBeGreaterThan(1.2)
    expect(letterRatio).toBeLessThan(1.35)
    // Letter is shorter than A4 → ratio decreased.
    expect(letterRatio).toBeLessThan(a4Ratio)
  })

  test('changing marginX 14 → 30 shrinks content width', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-page').click()

    const measure = async () =>
      page.evaluate(() => {
        const stage = document.querySelector('[data-testid="preview-stage"]') as HTMLElement | null
        if (!stage) return 0
        const inner = stage.querySelector('[data-testid="preview-content"]') as HTMLElement | null
        return inner ? inner.getBoundingClientRect().width : 0
      })

    const before = await measure()
    await page.getByTestId('page-margin-x').fill('30')
    await page.getByTestId('page-margin-x').press('Enter')
    await page.waitForTimeout(300)
    const after = await measure()
    expect(after).toBeLessThan(before)
  })

  test('toggling hideSectionIcons off reveals section heading icons', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-page').click()
    // Default is hideSectionIcons=true, so icons are hidden initially.
    const initiallyHidden = await page.evaluate(() => {
      const headings = Array.from(
        document.querySelectorAll('[data-section-id] [data-section-heading]'),
      ) as HTMLElement[]
      // If icons are hidden, the inner span[data-section-icon] is missing or has display:none.
      const iconSpans = document.querySelectorAll('[data-section-icon]')
      return iconSpans.length === 0
    })
    expect(initiallyHidden).toBe(true)

    // Toggle off.
    await page.getByTestId('page-hide-section-icons').click()
    await page.waitForTimeout(300)
    const afterToggle = await page.evaluate(
      () => document.querySelectorAll('[data-section-icon]').length,
    )
    expect(afterToggle).toBeGreaterThan(0)
  })

  test('reload → all page settings persisted', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-page').click()
    await page.getByTestId('page-format').selectOption('letter')
    await page.getByTestId('page-margin-x').fill('30')
    // Wait for autosave.
    await page.waitForTimeout(800)

    await page.reload()
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })
    await page.getByTestId('accordion-page').click()

    const fmt = await page
      .getByTestId('page-format')
      .evaluate((el) => (el as HTMLSelectElement).value)
    expect(fmt).toBe('letter')
    const mx = await page
      .getByTestId('page-margin-x')
      .evaluate((el) => (el as HTMLInputElement).value)
    expect(mx).toBe('30')
  })
})
/**
 * T149 — Playwright E2E: AI Analysis panel (S07, US14).
 *
 * Asserts the full AI Analysis flow:
 *  1. Open editor for a v2 resume that has content
 *  2. Open the right sidebar → "Analysis" accordion
 *  3. Click "Analyze" button
 *  4. Wait ≤ 60s for the result to render
 *  5. Verify: overall score + 10 dimension bars + ≥3 strengths + ≥3 suggestions
 *
 * Skips gracefully when the backend is not reachable so the suite
 * can still run on dev machines without the full stack.
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

async function registerAndCreateV2Resume(page: Page): Promise<string> {
  const stamp = Date.now()
  const email = `e2e032an-${stamp}@example.com`
  const password = 'Test1234!aaa'
  await page.goto(`${FRONTEND}/register`)
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.getByTestId('auth-submit').click()
  await page.waitForURL(/\/(dashboard|resumes)/, { timeout: 15_000 })
  // Login to obtain Bearer token (v2 API requires JWT, not cookie session)
  const loginRes = await page.request.post(`${BACKEND}/api/v1/auth/login`, {
    data: { email, password },
  })
  expect(loginRes.status(), `POST /auth/login → ${loginRes.status()}`).toBeLessThan(400)
  const loginBody = (await loginRes.json()) as { tokens?: { access_token?: string } }
  const token = loginBody.tokens?.access_token
  if (!token) throw new Error('No access_token returned from POST /auth/login')
  const apiRes = await page.request.post(`${BACKEND}/api/v1/v2/resumes`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `E2E Analyze ${stamp}`, slug: `e2e-an-${stamp}`, from_sample: true },
  })
  expect(apiRes.status(), `POST /v2/resumes → ${apiRes.status()}`).toBeLessThan(400)
  const body = (await apiRes.json()) as { resume?: { id: string }; id?: string }
  const id = body.resume?.id ?? body.id
  if (!id) throw new Error('No resume id returned from POST /v2/resumes')
  return id
}

test.describe('S07 — AI Analysis (US14)', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Backend not reachable — skipping AI analysis E2E')
    }
  })

  test('click Analyze shows score + 10 dimensions + strengths + suggestions', async ({ page }) => {
    const resumeId = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${resumeId}`)

    // Open right sidebar (in case collapsed)
    const toggleRight = page.getByTestId('toggle-right-sidebar')
    if ((await toggleRight.getAttribute('aria-pressed')) === 'true') {
      await toggleRight.click()
    }

    // Open Analysis accordion
    const analysisToggle = page.getByRole('button', { name: /^Analysis$/i })
    if (await analysisToggle.isVisible().catch(() => false)) {
      await analysisToggle.click()
    }

    // Click the Analyze button
    const analyzeBtn = page.getByRole('button', { name: /^Analyze$/ })
    await expect(analyzeBtn).toBeVisible({ timeout: 10_000 })
    await analyzeBtn.click()

    // Wait for the overall score gauge to appear (≤60s per spec)
    const scoreGauge = page.getByTestId('analysis-overall-score')
    await expect(scoreGauge).toBeVisible({ timeout: 60_000 })

    // Verify 10 dimension progress bars
    const dimBars = page.getByTestId('analysis-dimension-bar')
    await expect(dimBars).toHaveCount(10, { timeout: 10_000 })

    // Verify ≥3 strengths and ≥3 suggestions
    const strengths = page.getByTestId('analysis-strength')
    const suggestions = page.getByTestId('analysis-suggestion')
    await expect(strengths.first()).toBeVisible({ timeout: 10_000 })
    expect(await strengths.count()).toBeGreaterThanOrEqual(3)
    expect(await suggestions.count()).toBeGreaterThanOrEqual(3)
  })

  /**
   * T193 — SC-011: AI analysis response < 60s.
   *
   * Measure the time from Analyze click to result render. Assert
   * typical ≤ 30s, and p99 < 60s. With one sample, this test
   * asserts p99 < 60s (i.e. one call < 60s). Repeated runs are
   * needed to compute p99.
   */
  test('SC-011: AI analysis completes within 60s', async ({ page }) => {
    const resumeId = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${resumeId}`)

    const toggleRight = page.getByTestId('toggle-right-sidebar')
    if ((await toggleRight.getAttribute('aria-pressed')) === 'true') {
      await toggleRight.click()
    }
    const analysisToggle = page.getByRole('button', { name: /^Analysis$/i })
    if (await analysisToggle.isVisible().catch(() => false)) {
      await analysisToggle.click()
    }

    const analyzeBtn = page.getByRole('button', { name: /^Analyze$/ })
    await expect(analyzeBtn).toBeVisible({ timeout: 10_000 })
    const t0 = Date.now()
    await analyzeBtn.click()

    const scoreGauge = page.getByTestId('analysis-overall-score')
    await expect(scoreGauge).toBeVisible({ timeout: 60_000 })
    const elapsed = Date.now() - t0
    console.log(`SC-011 AI analysis elapsed: ${elapsed}ms`)
    // typical ≤ 30s
    if (elapsed > 30_000) {
      console.warn(`SC-011 typical (${elapsed}ms) > 30s — exceeds "typical" target`)
    }
    // p99 < 60s
    expect(elapsed).toBeLessThan(60_000)
  })
})

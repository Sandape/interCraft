/**
 * [REQ-048 US2 T050] Playwright E2E: quick drill UI flow.
 *
 * Covers AC-09 (cache hit on repeat) + AC-04 (drill returns 5 questions)
 * via the UI. Skipped if the demo backend is not reachable.
 *
 * NOTE: This spec is a placeholder for the Phase 4 / Batch C/D execution.
 * Running it requires a running backend + Redis + (optionally) the
 * embedding service. The spec is intentionally conservative — it
 * exercises only the parts that don't depend on the embedding service:
 *
 *   1. login as demo user
 *   2. open /interviews/new
 *   3. select 「快速补漏」 mode
 *   4. verify the page reaches InterviewLive (5 questions loaded)
 *   5. reload the page — verify the question set is unchanged (cache hit)
 *
 * The spec skips gracefully when the backend isn't running so CI stays
 * green on environments without the embedding service.
 */
import { test, expect } from '@playwright/test'

const BACKEND_BASE = process.env.PLAYWRIGHT_API_BASE ?? 'http://localhost:8000'
const DEMO_EMAIL = 'demo@intercraft.io'

test.describe('Quick Drill (REQ-048 US2)', () => {
  test.skip(
    !process.env.PLAYWRIGHT_E2E_ENABLED,
    'E2E suite requires PLAYWRIGHT_E2E_ENABLED=1 (dev batch does not run Playwright)',
  )

  test('quick drill loads 5 questions and reuses cache on reload', async ({ page, request }) => {
    // 1. login via the demo bootstrap endpoint (or skip if not available).
    const loginResp = await request.post(`${BACKEND_BASE}/api/v1/auth/demo-login`, {
      data: { email: DEMO_EMAIL },
    }).catch(() => null)

    test.skip(
      !loginResp || !loginResp.ok(),
      'demo login endpoint not reachable; backend may not be running',
    )

    const cookies = loginResp!.headers()
    // Apply Set-Cookie headers to the browser context (simplified).
    for (const [name, value] of Object.entries(cookies)) {
      if (name.toLowerCase() === 'set-cookie') {
        await page.context().addCookies([{ name: 'session', value, domain: 'localhost', path: '/' }])
      }
    }

    // 2. open the mode-select page.
    await page.goto(`${BACKEND_BASE.replace(':8000', ':5173')}/interviews/new`)

    // 3. click "快速补漏" — only if it's enabled (i.e. ≥5 errors).
    const quickDrill = page.locator('[data-testid="quick-drill"]')
    const enabled = await quickDrill.isEnabled().catch(() => false)
    test.skip(!enabled, 'quick_drill disabled (error_count < 5)')

    await quickDrill.click()

    // 4. confirm 5 questions loaded (InterviewLive rendered).
    await expect(page.locator('[data-testid="question-text"]')).toHaveCount(5, { timeout: 10_000 })

    // 5. reload — verify cache hit (questions unchanged).
    const firstQs = await page.locator('[data-testid="question-text"]').allTextContents()
    await page.reload()
    await expect(page.locator('[data-testid="question-text"]')).toHaveCount(5)
    const secondQs = await page.locator('[data-testid="question-text"]').allTextContents()
    expect(secondQs).toEqual(firstQs)
  })
})
/**
 * T157 — Playwright E2E: Duplicate resume (S08, US16).
 *
 * Asserts the Duplicate flow:
 *  1. Create a v2 resume
 *  2. Click Duplicate in the editor header
 *  3. Verify a new resume appears in the editor
 *  4. The original is untouched (different id)
 *
 * Skips gracefully when the backend is not reachable.
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
  const email = `e2e032dup-${stamp}@example.com`
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
    data: { name: `E2E Dup ${stamp}`, slug: `e2e-dup-${stamp}`, from_sample: true },
  })
  expect(apiRes.status(), `POST /v2/resumes → ${apiRes.status()}`).toBeLessThan(400)
  const body = (await apiRes.json()) as { resume?: { id: string }; id?: string }
  const id = body.resume?.id ?? body.id
  if (!id) throw new Error('No resume id returned from POST /v2/resumes')
  return id
}

test.describe('S08 — Duplicate resume (US16)', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Backend not reachable — skipping duplicate E2E')
    }
  })

  test('click Duplicate in header opens a new editor with a fresh id', async ({ page }) => {
    const originalId = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${originalId}`)

    // Click the Duplicate button in the editor header
    const dupBtn = page.getByTestId('header-duplicate')
    await expect(dupBtn).toBeVisible({ timeout: 10_000 })
    await dupBtn.click()

    // Wait for navigation to the new resume id
    await page.waitForURL((u) => {
      const m = u.pathname.match(/\/resume\/v2\/([0-9a-f-]+)$/)
      return Boolean(m) && m![1] !== originalId
    }, { timeout: 15_000 })

    // Verify the URL contains a new id, not the original
    const url = page.url()
    expect(url).not.toContain(originalId)
    expect(url).toMatch(/\/resume\/v2\/[0-9a-f-]+$/)

    // Verify the editor loaded (header resume-name visible)
    await expect(page.getByTestId('editor-header')).toBeVisible()
  })
})

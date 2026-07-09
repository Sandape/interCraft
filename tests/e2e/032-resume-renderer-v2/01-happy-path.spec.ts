/**
 * T098 — Playwright E2E: happy path with PDF + JSON download assertions.
 *
 * Created (T098) for US10 — extends the existing S01 (template switch +
 * editor basic) with two new assertions on the dock:
 *   1. Click "Download JSON" — a download is triggered with a `.json`
 *      extension and the body starts with `{`.
 *   2. Click "Download PDF" — a download is triggered with a `.pdf`
 *      extension and the response Content-Type is `application/pdf`.
 *
 * The backend export gateway is the 027 gateway
 * (`POST /api/v1/export/render`). The test short-circuits via
 * `test.skip()` when the backend is not reachable so the suite can
 * still run on dev machines without the full stack.
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
  const email = `e2e032-${stamp}@example.com`
  const password = 'Test1234!aaa'
  // Register
  await page.goto(`${FRONTEND}/register`)
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.getByTestId('auth-submit').click()
  await page.waitForURL(/\/(dashboard|resumes)/, { timeout: 15_000 })
  // Login to obtain Bearer token, then create v2 resume with the token
  const loginRes = await page.request.post(`${BACKEND}/api/v1/auth/login`, {
    data: { email, password },
  })
  expect(loginRes.status(), `POST /auth/login → ${loginRes.status()}`).toBeLessThan(400)
  const loginBody = (await loginRes.json()) as { tokens?: { access_token?: string } }
  const token = loginBody.tokens?.access_token
  if (!token) throw new Error('No access_token returned from POST /auth/login')
  // Create a v2 resume via the API (faster + more deterministic than UI)
  const apiRes = await page.request.post(`${BACKEND}/api/v1/v2/resumes`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `E2E ${stamp}`, slug: `e2e-${stamp}`, from_sample: true },
  })
  expect(apiRes.status(), `POST /v2/resumes → ${apiRes.status()}`).toBeLessThan(400)
  const body = (await apiRes.json()) as { resume?: { id: string }; id?: string }
  const id = body.resume?.id ?? body.id
  if (!id) throw new Error('No resume id returned from POST /v2/resumes')
  return id
}

test.describe('032-resume-renderer-v2 happy path (S01 + US10 T098)', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Backend not reachable — skipping T098 E2E (US10 dock export).')
    }
  })

  test('dock renders + JSON + PDF downloads work', async ({ page }) => {
    const resumeId = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${resumeId}`)
    // Wait for the dock toolbar to mount.
    await expect(page.getByTestId('dock')).toBeVisible({ timeout: 15_000 })

    // ── 1. JSON download ───────────────────────────────────────────────
    const [jsonDownload] = await Promise.all([
      page.waitForEvent('download', { timeout: 15_000 }),
      page.getByTestId('dock-download-json').click(),
    ])
    const jsonName = jsonDownload.suggestedFilename()
    expect(jsonName).toMatch(/\.json$/)
    const jsonPath = await jsonDownload.path()
    if (jsonPath) {
      const text = await (await import('node:fs/promises')).readFile(jsonPath, 'utf8')
      expect(text.trimStart().startsWith('{')).toBe(true)
    }

    // ── 2. PDF download ────────────────────────────────────────────────
    const [pdfDownload] = await Promise.all([
      page.waitForEvent('download', { timeout: 30_000 }),
      page.getByTestId('dock-download-pdf').click(),
    ])
    const pdfName = pdfDownload.suggestedFilename()
    expect(pdfName).toMatch(/-20\d{2}-\d{2}-\d{2}\.pdf$/)
    const pdfPath = await pdfDownload.path()
    if (pdfPath) {
      const buf = await (await import('node:fs/promises')).readFile(pdfPath)
      // PDF magic number "%PDF-"
      expect(buf.subarray(0, 5).toString('ascii')).toBe('%PDF-')
    }
  })
})

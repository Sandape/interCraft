/**
 * REQ-RESUME-FIX-1 — Onyx template renders 6 long-tail sections
 * (Interests / Awards / Certifications / Publications / Volunteer / References).
 *
 * Strategy: log in as demo, navigate to a resume, switch to Onyx template,
 * then use the v2 API to inject items into each of the 6 sections, reload,
 * and assert the preview pane exposes the corresponding data-testids.
 *
 * Skips gracefully if backend or frontend is not reachable.
 */
import { test, expect, type Page } from '@playwright/test'

const FRONTEND = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173'
const BACKEND = process.env.PLAYWRIGHT_API_BASE ?? 'http://127.0.0.1:8000'

async function isUp(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { method: 'GET' })
    return res.status < 500
  } catch {
    return false
  }
}

test.describe('REQ-RESUME-FIX-1 — Onyx 6 sections', () => {
  test.beforeAll(async () => {
    if (!(await isUp(`${FRONTEND}/`))) {
      test.skip(true, 'Frontend not reachable — skipping REQ-RESUME-FIX-1 E2E.')
    }
    if (!(await isUp(`${BACKEND}/api/v1/openapi.json`))) {
      test.skip(true, 'Backend not reachable — skipping REQ-RESUME-FIX-1 E2E.')
    }
  })

  test('preview shows all 6 onyx sections when items are seeded', async ({ page }) => {
    // Log in as demo
    await page.goto(`${FRONTEND}/login`)
    await page.getByTestId('email-input').fill('demo@intercraft.io')
    await page.getByTestId('password-input').fill('Demo1234')
    await page.getByTestId('auth-submit').click()
    await page.waitForURL(/\/(dashboard|resumes)/, { timeout: 15_000 })

    // Obtain demo token via API
    const loginRes = await page.request.post(`${BACKEND}/api/v1/auth/login`, {
      data: { email: 'demo@intercraft.io', password: 'Demo1234' },
    })
    expect(loginRes.status(), `demo login → ${loginRes.status()}`).toBeLessThan(400)
    const loginBody = (await loginRes.json()) as { tokens?: { access_token?: string } }
    const token = loginBody.tokens?.access_token
    if (!token) throw new Error('No access_token for demo user')

    // Create a fresh v2 resume from sample
    const stamp = Date.now()
    const createRes = await page.request.post(`${BACKEND}/api/v1/v2/resumes`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `FIX1-${stamp}`, slug: `fix1-${stamp}`, from_sample: true },
    })
    expect(createRes.status(), `create v2 → ${createRes.status()}`).toBeLessThan(400)
    const created = (await createRes.json()) as { resume?: { id: string }; id?: string }
    const resumeId = created.resume?.id ?? created.id
    if (!resumeId) throw new Error('No resume id returned')

    // Read current resume data and seed 6 sections with items
    const readRes = await page.request.get(`${BACKEND}/api/v1/v2/resumes/${resumeId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(readRes.status(), `read v2 → ${readRes.status()}`).toBeLessThan(400)
    const resumeBody = (await readRes.json()) as {
      resume?: { data?: Record<string, unknown>; version?: number }
      data?: Record<string, unknown>
      version?: number
    }
    const data: any = resumeBody.resume?.data ?? resumeBody.data ?? {}
    const currentVersion = resumeBody.resume?.version ?? resumeBody.version
    if (typeof currentVersion !== 'number') {
      throw new Error('No version returned from GET /v2/resumes/:id')
    }

    const sections = (data.sections ?? {}) as Record<string, any>
    sections.interests = {
      ...(sections.interests ?? {}),
      hidden: false,
      items: [
        { id: 'i-1', hidden: false, icon: '', iconColor: '', name: 'Photography', keywords: ['portrait', 'street'] },
      ],
    }
    sections.awards = {
      ...(sections.awards ?? {}),
      hidden: false,
      items: [
        {
          id: 'a-1', hidden: false, title: 'Best Paper', awarder: 'NeurIPS',
          date: '2024', website: { url: '', label: '', inlineLink: false },
          description: 'For novel approach',
        },
      ],
    }
    sections.certifications = {
      ...(sections.certifications ?? {}),
      hidden: false,
      items: [
        {
          id: 'c-1', hidden: false, title: 'AWS SA', issuer: 'AWS',
          date: '2023', website: { url: '', label: '', inlineLink: false },
          description: 'Pro',
        },
      ],
    }
    sections.publications = {
      ...(sections.publications ?? {}),
      hidden: false,
      items: [
        {
          id: 'p-1', hidden: false, title: 'On Indexing', publisher: 'ACM',
          date: '2022', website: { url: '', label: '', inlineLink: false },
          description: 'Peer-reviewed',
        },
      ],
    }
    sections.volunteer = {
      ...(sections.volunteer ?? {}),
      hidden: false,
      items: [
        {
          id: 'v-1', hidden: false, organization: 'Code for Good',
          location: 'Remote', period: '2020 — 2022',
          website: { url: '', label: '', inlineLink: false },
          description: 'Mentoring students',
        },
      ],
    }
    sections.references = {
      ...(sections.references ?? {}),
      hidden: false,
      items: [
        {
          id: 'r-1', hidden: false, name: 'Dr. Hopper',
          position: 'Principal Engineer',
          website: { url: '', label: '', inlineLink: false },
          phone: '+1-555-0100', description: 'Direct manager',
        },
      ],
    }
    data.sections = sections

    // Switch to Onyx template
    data.metadata = { ...(data.metadata ?? {}), template: 'onyx' }

    const putRes = await page.request.put(`${BACKEND}/api/v1/v2/resumes/${resumeId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'If-Match': String(currentVersion),
      },
      data: { data },
    })
    expect(putRes.status(), `put v2 → ${putRes.status()}`).toBeLessThan(400)

    // Visit the editor page and wait for the preview pane
    await page.goto(`${FRONTEND}/resume/v2/${resumeId}`)
    await expect(page.getByTestId('dock')).toBeVisible({ timeout: 20_000 })

    // Wait for at least one of the 6 section testids to appear
    await expect(page.locator('[data-testid="onyx-volunteer"]').first()).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('[data-testid="onyx-references"]').first()).toBeVisible({ timeout: 5_000 })

    // Assert all 6 are present in the DOM
    await expect(page.locator('[data-testid="onyx-interests"]')).toHaveCount(1)
    await expect(page.locator('[data-testid="onyx-awards"]')).toHaveCount(1)
    await expect(page.locator('[data-testid="onyx-certifications"]')).toHaveCount(1)
    await expect(page.locator('[data-testid="onyx-publications"]')).toHaveCount(1)
    await expect(page.locator('[data-testid="onyx-volunteer"]')).toHaveCount(1)
    await expect(page.locator('[data-testid="onyx-references"]')).toHaveCount(1)

    // Spot-check content presence
    const html = await page.content()
    expect(html).toContain('Photography')
    expect(html).toContain('Best Paper')
    expect(html).toContain('AWS SA')
    expect(html).toContain('On Indexing')
    expect(html).toContain('Code for Good')
    expect(html).toContain('Dr. Hopper')
  })
})
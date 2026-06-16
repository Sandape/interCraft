/**
 * E2E: Jobs status alignment (Feature 015).
 * Covers US1 (advance via popover, no 409), US2 (real status tabs),
 * US3 (withdrawn vs rejected stats), US4 (409 inline retry), and the
 * "no phantom tabs" final assertion.
 */
import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

// Backend running on 8002 (the existing dev server on 8000 is stale and
// predates the `/api/v1/jobs/transitions` route added for Feature 015).
const API_URL = process.env.E2E_API_URL ?? 'http://127.0.0.1:8002/api/v1'

function makeUser(suffix: string) {
  return {
    email: `e2e-015-${suffix}@intercraft-e2e.com`,
    password: 'P@ssw0rd1234',
    display_name: `E2E 015 ${suffix}`,
  }
}

function freshSuffix(): string {
  return `${Date.now()}-${Math.floor(Math.random() * 100_000)}`
}

async function authRegister(
  request: APIRequestContext,
  user: { email: string; password: string; display_name: string },
): Promise<string> {
  const res = await request.post(`${API_URL}/auth/register`, { data: user })
  expect([200, 201]).toContain(res.status())
  const body = await res.json()
  const token = body.tokens?.access_token || body.access_token
  expect(token).toBeTruthy()
  return token as string
}

async function seedJob(request: APIRequestContext, token: string, company: string, position: string) {
  const res = await request.post(`${API_URL}/jobs`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { company, position },
  })
  expect(res.status()).toBe(201)
  return (await res.json()) as { id: string; status: string }
}

async function patchStatus(request: APIRequestContext, token: string, jobId: string, to: string) {
  const res = await request.patch(`${API_URL}/jobs/${jobId}/status`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { to },
  })
  expect(res.status()).toBe(200)
}

async function prepareSession(page: Page, token: string) {
  await page.addInitScript((t: string) => {
    sessionStorage.setItem('ic.access_token', t)
    sessionStorage.setItem('ic.refresh_token', t)
  }, token)
}

test.describe.serial('Feature 015 — Jobs status alignment', () => {
  test('US1: advances a job from applied to test via the popover with no 409', async ({ page, request }) => {
    const token = await authRegister(request, makeUser(`u1-${freshSuffix()}`))
    const job = await seedJob(request, token, '字节跳动', '高级前端工程师')
    await prepareSession(page, token)

    const responses409: string[] = []
    page.on('response', (resp) => {
      if (resp.status() === 409) responses409.push(resp.url())
    })

    await page.goto('/jobs')
    await expect(page.locator('h1')).toContainText('求职追踪')

    const row = page.locator(`[data-testid="job-row-${job.id}"]`)
    await expect(row).toBeVisible()

    await row.locator('[data-testid="status-popover-trigger"]').click()
    await expect(row.locator('[data-testid="status-popover-menu"]')).toBeVisible()

    await row.locator('[data-testid="status-menuitem-test"]').click()
    await expect(row).toContainText('笔试', { timeout: 5_000 })
    await expect(page.locator('[data-testid="status-tab-count-test"]')).toHaveText('1')

    expect(responses409).toEqual([])
  })

  test('US2: filter tabs match the real status set and counts are accurate', async ({ page, request }) => {
    const token = await authRegister(request, makeUser(`u2-${freshSuffix()}`))
    const j1 = await seedJob(request, token, 'A公司', '工程师')
    const j2 = await seedJob(request, token, 'B公司', '工程师')
    await patchStatus(request, token, j2.id, 'test')
    await prepareSession(page, token)

    await page.goto('/jobs')
    await expect(page.locator('[data-testid="status-tab-applied"]')).toBeVisible()
    await expect(page.locator('[data-testid="status-tab-test"]')).toBeVisible()
    await expect(page.locator('[data-testid="status-tab-count-applied"]')).toHaveText('1')
    await expect(page.locator('[data-testid="status-tab-count-test"]')).toHaveText('1')

    await page.locator('[data-testid="status-tab-test"]').click()
    await expect(page.locator(`[data-testid="job-row-${j1.id}"]`)).toHaveCount(0)
    await expect(page.locator(`[data-testid="job-row-${j2.id}"]`)).toBeVisible()
  })

  test('US3: withdrawn and rejected show as separate stats (2 vs 1)', async ({ page, request }) => {
    const token = await authRegister(request, makeUser(`u3-${freshSuffix()}`))
    // 3 jobs: 2 withdrawn + 1 rejected (spec: "split withdrawn from rejected")
    const j1 = await seedJob(request, token, 'C1公司', '工程师')
    const j2 = await seedJob(request, token, 'C2公司', '工程师')
    const j3 = await seedJob(request, token, 'D公司', '工程师')
    await patchStatus(request, token, j1.id, 'withdrawn')
    await patchStatus(request, token, j2.id, 'withdrawn')
    await patchStatus(request, token, j3.id, 'rejected')
    await prepareSession(page, token)

    await page.goto('/jobs', { waitUntil: 'networkidle' })
    // Both rows visible
    await expect(page.locator(`[data-testid="job-row-${j1.id}"]`)).toBeVisible({ timeout: 10_000 })
    await expect(page.locator(`[data-testid="job-row-${j3.id}"]`)).toBeVisible({ timeout: 10_000 })

    // Tab counts reflect the seed: 2 withdrawn, 1 rejected
    await expect(page.locator('[data-testid="status-tab-count-withdrawn"]')).toHaveText('2')
    await expect(page.locator('[data-testid="status-tab-count-rejected"]')).toHaveText('1')

    // The "已撤回" stat tile should show 2 and the "已拒绝" tile should show 1
    // (locate each tile by its label text and inspect its parent card's numeric value)
    const withdrawnCard = page.locator('div').filter({ has: page.locator('text=/^已撤回$/') }).first()
    const rejectedCard = page.locator('div').filter({ has: page.locator('text=/^已拒绝$/') }).first()
    await expect(withdrawnCard).toContainText('2')
    await expect(rejectedCard).toContainText('1')
  })

  test('US4: 409 surfaces inline error with retry affordance', async ({ page, request }) => {
    const token = await authRegister(request, makeUser(`u4-${freshSuffix()}`))
    const job = await seedJob(request, token, 'E公司', '工程师')
    await prepareSession(page, token)

    // Force the status PATCH to return 409
    await page.route(`**/api/v1/jobs/${job.id}/status`, async (route) => {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'job.invalid_transition', message: 'invalid status transition' } }),
      })
    })

    await page.goto('/jobs')
    const row = page.locator(`[data-testid="job-row-${job.id}"]`)
    await expect(row).toBeVisible()

    // Open popover, click an allowed transition
    await row.locator('[data-testid="status-popover-trigger"]').click()
    await row.locator('[data-testid="status-menuitem-test"]').click()

    // The popover closes on selection. The error UI lives inside the popover
    // (StatusPopover.tsx renders the error block only when `open === true`),
    // so we have to reopen the popover to inspect it.
    await expect(row.locator('[data-testid="status-popover-menu"]')).toHaveCount(0)
    await row.locator('[data-testid="status-popover-trigger"]').click()

    // Inline error + retry affordance both visible
    const err = row.locator(`[data-testid="row-error-${job.id}"]`)
    await expect(err).toBeVisible({ timeout: 5_000 })
    await expect(err).toContainText('invalid status transition')
    await expect(row.locator('[data-testid="status-popover-retry"]')).toBeVisible()

    // Row badge must NOT have advanced to "笔试"
    await expect(row.locator(`[data-testid="status-badge-${job.id}"]`)).not.toContainText('笔试')

    // Unroute and retry — the real backend should accept the transition
    await page.unroute(`**/api/v1/jobs/${job.id}/status`)
    await row.locator('[data-testid="status-popover-retry"]').click()

    // Badge advances to "笔试" on success
    await expect(row).toContainText('笔试', { timeout: 10_000 })
  })

  test('no phantom tabs: only the 7 real statuses are rendered', async ({ page, request }) => {
    const token = await authRegister(request, makeUser(`u5-${freshSuffix()}`))
    await prepareSession(page, token)

    await page.goto('/jobs')
    for (const k of ['all', 'applied', 'test', 'oa', 'hr', 'offer', 'rejected', 'withdrawn']) {
      await expect(page.locator(`[data-testid="status-tab-${k}"]`)).toBeVisible()
    }
    // Phantom tabs must not exist
    await expect(page.locator('[data-testid="status-tab-screening"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="status-tab-interview"]')).toHaveCount(0)

    // Phantom strings must not appear in the status-tabs / row / stats area
    // (the side-nav still has an `/interview` link, which is unrelated)
    const jobsArea = page.locator('main')
    const jobsText = await jobsArea.innerText()
    expect(jobsText).not.toMatch(/screening|interview|简历筛选|面试中/)
  })
})

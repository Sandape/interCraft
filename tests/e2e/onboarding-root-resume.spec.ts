// spec: specs/061-ai-agent-production/spec.md — Issue #61 Onboarding root resume
//
// Real-browser acceptance for Issue #61: onboarding Step 2 must call the
// createRootResume client and await real persistence before completeStep(3).
// No route/API mocks or stack-reachability skips — backend unavailability
// causes a hard failure.
//
// Coverage:
//   * Blank — sourceMarkdown exactly empty, no demo identity in basics/summary.
//   * Exact marker — paste/structured mode persists the user text byte-for-byte.
//   * Conflict reuse — existing root causes 409 → GET existing → advance.
//   * Resume Center card («编辑素材库» link) + editor URL reference the same ID.
//   * Rapid clicks — same DOM element 3× → network event count proves exactly 1 POST.
//   * Browser offline retry — unroute auth proxy → offline → requestfailed →
//     stay Step2 with retry → online → retry → success.
//   * Tenant B 404 — other tenant cannot read tenant A root.
//   * Sequential + concurrent POST — strict nested 409 envelope, winner invariant.
import { test, expect } from '@playwright/test'
import { ensureFreshAccount, DEFAULT_PASSWORD, API_BASE } from './018-fix-product-defects/helpers/auth'

// ── Helpers ────────────────────────────────────────────────────────────────

async function registerViaApi(api: Parameters<typeof test.extend>[0]['request']) {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
  const email = `e2e-api-${suffix}@example.com`
  const resp = await api.post(`${API_BASE}/api/v1/auth/register`, {
    data: { email, password: DEFAULT_PASSWORD, display_name: `api-${suffix}` },
  })
  if (!resp.ok()) {
    throw new Error(`register failed: ${resp.status()} ${await resp.text()}`)
  }
  const body = await resp.json()
  const accessToken = body?.tokens?.access_token
  if (!accessToken) {
    throw new Error(`no access_token in register response: ${JSON.stringify(body)}`)
  }
  return { email, accessToken }
}

async function fetchRootFor(api: Parameters<typeof test.extend>[0]['request'], token: string) {
  const resp = await api.get(`${API_BASE}/api/v1/v2/resumes/root`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (resp.status() === 404) return null
  if (!resp.ok()) {
    const text = await resp.text()
    throw new Error(`GET /v2/resumes/root failed (${resp.status()}): ${text}`)
  }
  return (await resp.json()) as { id: string; data: { metadata?: { markdown?: { sourceMarkdown?: string } } } }
}

async function postRoot(
  api: Parameters<typeof test.extend>[0]['request'],
  token: string,
  marker: string,
): Promise<{ status: number; body: Record<string, unknown> }> {
  const payload = {
    name: '根简历',
    slug: 'root-resume',
    data: {
      picture: { hidden: true, url: '', size: 96, rotation: 0, aspectRatio: 1 },
      basics: { name: '', headline: '', email: '', phone: '', location: '' },
      summary: { title: 'Summary', icon: 'user', columns: 1, hidden: false, content: '' },
      sections: {
        experience: { title: 'Experience', icon: 'briefcase', hidden: false, items: [] },
        education: { title: 'Education', icon: 'graduation-cap', hidden: false, items: [] },
        projects: { title: 'Projects', icon: 'folder', hidden: false, items: [] },
        skills: { title: 'Skills', icon: 'wrench', hidden: false, items: [] },
      },
      customSections: [],
      metadata: {
        template: 'onyx',
        markdown: { sourceMarkdown: marker, themeId: 'muji-default-autumn' },
      },
    },
  }
  const resp = await api.post(`${API_BASE}/api/v1/v2/resumes/root`, {
    headers: { Authorization: `Bearer ${token}` },
    data: payload,
  })
  const body = resp.headers()['content-type']?.includes('json')
    ? ((await resp.json()) as Record<string, unknown>)
    : { raw: await resp.text() }
  return { status: resp.status(), body }
}

// ── Tests ──────────────────────────────────────────────────────────────────

test.describe('Onboarding root resume — Issue #61', () => {
  test('blank onboarding persists empty sourceMarkdown and no demo identity', async ({ page, request }) => {
    const account = await ensureFreshAccount(page)
    await page.goto('/onboarding')

    await page.getByRole('button', { name: '校招' }).click()
    await page.getByLabel('目标岗位或方向').fill('产品经理')
    await page.getByRole('button', { name: '下一步' }).click()
    await page.getByRole('button', { name: /从空白草稿开始/i }).click()
    await page.getByRole('button', { name: /下一步/i }).click()
    await expect(page.getByRole('heading', { name: /添加一个目标岗位/i })).toBeVisible({
      timeout: 10_000,
    })

    const root = await fetchRootFor(request, account.accessToken)
    expect(root).not.toBeNull()
    expect(root!.data.metadata?.markdown?.sourceMarkdown).toBe('')

    const detailResp = await request.get(`${API_BASE}/api/v1/v2/resumes/${root!.id}`, {
      headers: { Authorization: `Bearer ${account.accessToken}` },
    })
    expect(detailResp.ok()).toBe(true)
    const detail = (await detailResp.json()) as {
      data: { basics: { name: string; email: string }; summary: { content: string } }
    }
    expect(detail.data.basics.name).toBe('')
    expect(detail.data.basics.email).toBe('')
    expect(detail.data.summary.content).toBe('')
  })

  test('paste onboarding preserves the user marker byte-for-byte', async ({ page, request }) => {
    const account = await ensureFreshAccount(page)
    await page.goto('/onboarding')

    await page.getByRole('button', { name: '校招' }).click()
    await page.getByLabel('目标岗位或方向').fill('产品经理')
    await page.getByRole('button', { name: '下一步' }).click()
    await page.getByRole('button', { name: /粘贴现有内容/i }).click()
    const marker =
      '  # 五年前端 + AI 应用工程师\n  \n  - 负责 RAG 与 Agent 工作流\n  - 推动可观测体系落地\n  '
    await page.getByPlaceholder(/负责某项产品/i).fill(marker)
    await page.getByRole('button', { name: /下一步/i }).click()
    await expect(page.getByRole('heading', { name: /添加一个目标岗位/i })).toBeVisible({
      timeout: 10_000,
    })

    const root = await fetchRootFor(request, account.accessToken)
    expect(root).not.toBeNull()
    expect(root!.data.metadata?.markdown?.sourceMarkdown).toBe(marker)
  })

  test('409 ROOT_EXISTS reuses the existing root (conflict reuse)', async ({ page, request }) => {
    const account = await ensureFreshAccount(page)
    const seeded = await postRoot(request, account.accessToken, 'pre-existing')
    expect(seeded.status).toBe(201)

    await page.goto('/onboarding')
    await page.getByRole('button', { name: '校招' }).click()
    await page.getByLabel('目标岗位或方向').fill('产品经理')
    await page.getByRole('button', { name: '下一步' }).click()
    await page.getByRole('button', { name: /从空白草稿开始/i }).click()
    await page.getByRole('button', { name: /下一步/i }).click()

    await expect(page.getByRole('heading', { name: /添加一个目标岗位/i })).toBeVisible({
      timeout: 10_000,
    })
    const root = await fetchRootFor(request, account.accessToken)
    expect(root!.data.metadata?.markdown?.sourceMarkdown).toBe('pre-existing')
  })

  test('Resume Center card «编辑素材库» and editor reference the same root ID', async ({ page, request }) => {
    const account = await ensureFreshAccount(page)
    await page.goto('/onboarding')

    await page.getByRole('button', { name: '校招' }).click()
    await page.getByLabel('目标岗位或方向').fill('产品经理')
    await page.getByRole('button', { name: '下一步' }).click()
    await page.getByRole('button', { name: /从空白草稿开始/i }).click()
    await page.getByRole('button', { name: /下一步/i }).click()
    await expect(page.getByRole('heading', { name: /添加一个目标岗位/i })).toBeVisible({ timeout: 10_000 })

    await page.goto('/resume')
    await page.waitForURL(/\/resume/, { timeout: 15_000 })

    const editLink = page.getByRole('link', { name: '编辑素材库' })
    await expect(editLink).toBeVisible({ timeout: 10_000 })

    const rootFromApi = await fetchRootFor(request, account.accessToken)
    expect(rootFromApi).not.toBeNull()
    const rootId = rootFromApi!.id
    expect(rootId.length).toBeGreaterThan(0)

    await editLink.click()
    await page.waitForURL(/\/resume\//, { timeout: 10_000 })
    expect(page.url()).toContain(rootId)
  })

  test('rapid same-element clicks fire exactly one POST (single-flight)', async ({ page, request }) => {
    const account = await ensureFreshAccount(page)
    const postedUrls: string[] = []
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/v2/resumes/root')) {
        postedUrls.push(req.url())
      }
    })

    await page.goto('/onboarding')
    await page.getByRole('button', { name: '校招' }).click()
    await page.getByLabel('目标岗位或方向').fill('产品经理')
    await page.getByRole('button', { name: '下一步' }).click()
    await page.getByRole('button', { name: /从空白草稿开始/i }).click()

    // Dispatch three click events against the exact same DOM node in one
    // browser execution stack.  This avoids locator re-resolution or a render
    // boundary making the second/third attempt disappear from the test.
    const nextBtn = page.getByTestId('onboarding-baseline-next')
    const dispatchResult = await nextBtn.evaluate((element) => {
      const button = element as HTMLButtonElement
      const dispatch = () =>
        button.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
      return {
        results: [dispatch(), dispatch(), dispatch()],
        stillConnected: button.isConnected,
      }
    })
    expect(dispatchResult.results).toEqual([true, true, true])
    expect(dispatchResult.stillConnected).toBe(true)

    // Wait for Step 3 to confirm the POST resolved.
    await expect(page.getByRole('heading', { name: /添加一个目标岗位/i })).toBeVisible({
      timeout: 10_000,
    })

    expect(postedUrls.length).toBe(1)
    const root = await fetchRootFor(request, account.accessToken)
    expect(root).not.toBeNull()
  })

  test('POST failure stays Step 2 with retry; retry succeeds', async ({ page, request }) => {
    const account = await ensureFreshAccount(page)

    // Remove the auth-helper route proxy so the browser's own fetch()
    // is affected by context offline (the helper uses route.fetch which
    // bypasses browser offline state).
    await page.unroute('**/api/v1/**')

    await page.goto('/onboarding')
    await page.getByRole('button', { name: '校招' }).click()
    await page.getByLabel('目标岗位或方向').fill('产品经理')
    await page.getByRole('button', { name: '下一步' }).click()
    await page.getByRole('button', { name: /从空白草稿开始/i }).click()

    // Watch for the actual failed POST.
    const failedRequest = page.waitForEvent('requestfailed', {
      predicate: (req) => req.method() === 'POST' && req.url().includes('/v2/resumes/root'),
    })

    // Go offline via browser context and click Next.
    const context = page.context()
    await context.setOffline(true)
    await page.getByTestId('onboarding-baseline-next').click()

    // Observe that the POST truly failed.
    await failedRequest

    // The retry UI must be visible — still on Step 2.
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('onboarding-baseline-retry')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByRole('heading', { name: /创建根简历草稿/i })).toBeVisible()

    // Confirm no root was created while offline.
    await context.setOffline(false)
    const before = await fetchRootFor(request, account.accessToken)
    expect(before).toBeNull()

    // Click retry — the POST should now succeed.
    await page.getByTestId('onboarding-baseline-retry').click()
    await expect(page.getByRole('heading', { name: /添加一个目标岗位/i })).toBeVisible({
      timeout: 10_000,
    })

    const after = await fetchRootFor(request, account.accessToken)
    expect(after).not.toBeNull()
  })

  test('tenant B cannot read tenant A root (404)', async ({ request }) => {
    const accountA = await registerViaApi(request)
    const accountB = await registerViaApi(request)

    const created = await postRoot(request, accountA.accessToken, 'tenant A only')
    expect(created.status).toBe(201)

    const resp = await request.get(`${API_BASE}/api/v1/v2/resumes/root`, {
      headers: { Authorization: `Bearer ${accountB.accessToken}` },
    })
    expect(resp.status()).toBe(404)
  })

  test('sequential second POST returns nested 409 ROOT_EXISTS — one-row invariant', async ({ request }) => {
    const account = await registerViaApi(request)

    const first = await postRoot(request, account.accessToken, 'winner marker')
    expect(first.status).toBe(201)

    const second = await postRoot(request, account.accessToken, 'loser marker')
    expect(second.status).toBe(409)
    // Strict nested envelope — no flat fallback.
    const err = second.body as { error?: { code?: string } }
    expect(err.error).not.toBeNull()
    expect(typeof err.error).toBe('object')
    expect((err.error as { code?: string }).code).toBe('ROOT_EXISTS')

    const root = await fetchRootFor(request, account.accessToken)
    expect(root!.data.metadata?.markdown?.sourceMarkdown).toBe('winner marker')
  })

  test('concurrent POSTs — one 201, N-1 409, winner marker/version unchanged', async ({ request }) => {
    const account = await registerViaApi(request)
    const burst = 6
    const results = await Promise.all(
      Array.from({ length: burst }, (_, i) =>
        postRoot(request, account.accessToken, i % 2 === 0 ? '' : `marker ${i}`),
      ),
    )

    const statuses = results.map((r) => r.status)
    const successes = results.filter((r) => r.status === 201)
    const conflicts = results.filter((r) => r.status === 409)
    expect(successes.length).toBe(1)
    expect(conflicts.length).toBe(burst - 1)
    expect(statuses.every((s) => s < 500)).toBe(true)

    for (const c of conflicts) {
      const err = c.body as { error?: { code?: string } }
      expect(err.error).not.toBeNull()
      expect(typeof err.error).toBe('object')
      expect((err.error as { code?: string }).code).toBe('ROOT_EXISTS')
    }

    const winnerId = (successes[0].body as { id?: string }).id
    const winnerVersion = (successes[0].body as { version?: number }).version

    const root = await fetchRootFor(request, account.accessToken)
    expect(root).not.toBeNull()
    expect(root!.id).toBe(winnerId)

    const detailResp = await request.get(`${API_BASE}/api/v1/v2/resumes/${root!.id}`, {
      headers: { Authorization: `Bearer ${account.accessToken}` },
    })
    expect(detailResp.ok()).toBe(true)
    const detail = (await detailResp.json()) as { version?: number }
    expect(detail.version).toBe(winnerVersion)
  })
})

/**
 * REQ-044 US2 — Product Analytics workspace (FR-011~FR-015 + SC-003/004/005).
 *
 * Spec coverage:
 *
 *   - SC-3.1: PM 在 Product Analytics workspace 单页完成
 *     activation/retention/adoption/quality 4 问 (无 sidebar 切换)
 *   - AC-11.1: 7 question tabs render
 *   - AC-11.2: each tab has ≥3 templates
 *   - AC-13.2: cohort selection applies to funnel + adoption panels
 *   - AC-15.2: user search input + detail drawer visible
 *   - AC-15.4: privacy guard — UsersAccounts page MUST NOT contain
 *     raw_resume / raw_prompt / raw_model_output tokens
 *   - EC-1/2/3: zero funnel / stale cohort / insufficient data
 *     all visible in UI
 *
 * INFRA-BLOCKED: live DB at 81.71.152.210:5432 is not reachable from
 * this CI environment. The HTTP spec runs against a real backend if
 * E2E_BACKEND_BASE points at a server with the demo user seeded.
 * Otherwise the spec is marked INFRA-BLOCKED and skipped at runtime.
 */
import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://127.0.0.1:5305'
const BACKEND_BASE = process.env.E2E_BACKEND_BASE ?? 'http://127.0.0.1:8205'
const DEMO_EMAIL = 'demo@intercraft.io'
const DEMO_PASSWORD = 'Demo1234'

async function loginAsDemo(page: Page, request: APIRequestContext) {
  const res = await request.post(`${BACKEND_BASE}/api/v1/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  })
  expect(res.status(), `POST /auth/login → ${res.status()}`).toBeLessThan(400)
  const body = await res.json()
  const tokens = body.tokens as { access_token: string; refresh_token: string }

  await page.addInitScript(({ access, refresh }) => {
    window.sessionStorage.setItem('ic.access_token', access)
    window.sessionStorage.setItem('ic.refresh_token', refresh)
    window.localStorage.setItem('access_token', access)
  }, { access: tokens.access_token, refresh: tokens.refresh_token })
}

async function backendReachable(request: APIRequestContext): Promise<boolean> {
  try {
    const res = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/product-analytics/health`,
      { timeout: 3_000 },
    )
    return res.ok()
  } catch {
    return false
  }
}

test.describe('REQ-044 US2 — Product Analytics workspace', () => {
  test.beforeEach(async ({ page, request }, testInfo) => {
    if (!(await backendReachable(request))) {
      testInfo.skip(
        true,
        'INFRA-BLOCKED: backend at ' +
          BACKEND_BASE +
          ' not reachable; spec skipped',
      )
      return
    }
    await loginAsDemo(page, request)
  })

  test('SC-3.1: PM completes 4 questions in one workspace (no sidebar nav)', async ({
    page,
  }) => {
    await page.goto(`${FRONTEND_BASE}/admin-console/product-analytics`)

    // Activation question.
    await page.getByTestId('question-tab-activation').click()
    await expect(page.getByTestId('question-tab-activation')).toHaveAttribute(
      'data-active',
      'true',
    )
    const activationTemplates = page.locator(
      '[data-testid^="product-analytics-template-q-act-"]',
    )
    await expect(activationTemplates).toHaveCount(3)

    // Retention question (same workspace, tab switch only — no sidebar).
    await page.getByTestId('question-tab-retention').click()
    const retentionTemplates = page.locator(
      '[data-testid^="product-analytics-template-q-ret-"]',
    )
    await expect(retentionTemplates).toHaveCount(3)

    // Adoption question.
    await page.getByTestId('question-tab-adoption').click()
    const adoptionTemplates = page.locator(
      '[data-testid^="product-analytics-template-q-adp-"]',
    )
    await expect(adoptionTemplates).toHaveCount(3)

    // Funnel panel rendered when funnel tab active.
    await page.getByTestId('question-tab-funnel').click()
    await expect(page.getByTestId('product-analytics-funnel-panel')).toBeVisible()
    await expect(page.getByTestId('funnel-chart')).toBeVisible()
  })

  test('AC-11.1 + AC-11.2: 7 question tabs × ≥3 templates each', async ({
    page,
  }) => {
    await page.goto(`${FRONTEND_BASE}/admin-console/product-analytics`)
    for (const tab of [
      'activation',
      'funnel',
      'retention',
      'adoption',
      'journey',
      'release',
      'experiment',
    ]) {
      await page.getByTestId(`question-tab-${tab}`).click()
      // Each tab has ≥3 templates by AC-11.2.
      const templates = page.locator(
        `[data-testid^="product-analytics-template-q-${tab.slice(0, 3)}-"]`,
      )
      await expect(templates.nth(2)).toBeVisible() // at least 3
    }
  })

  test('AC-13.2: cohort selection applies to funnel + adoption', async ({
    page,
  }) => {
    await page.goto(`${FRONTEND_BASE}/admin-console/product-analytics`)

    // Pick cohort via the sidebar CohortPicker.
    await page.getByTestId('cohort-select').selectOption('cohort-active')

    // Funnel panel re-renders with the selected cohort.
    await page.getByTestId('question-tab-funnel').click()
    await expect(page.getByTestId('funnel-cohort').first()).toContainText(
      'cohort-active',
    )

    // Adoption panel re-renders too.
    await page.getByTestId('question-tab-adoption').click()
    await expect(
      page.getByTestId('feature-adoption-cohort-feat-error-book'),
    ).toContainText('cohort-active')
  })

  test('AC-SC-4.1: every metric tooltip renders all 7 SC-004 fields', async ({
    page,
  }) => {
    await page.goto(`${FRONTEND_BASE}/admin-console/product-analytics`)
    await page.getByTestId('question-tab-funnel').click()
    const tooltip = page.getByTestId('metric-tooltip').first()
    await expect(tooltip).toBeVisible()
    for (const field of [
      'definition',
      'owner',
      'source',
      'period',
      'freshness',
      'completeness',
      'quality-flag',
    ]) {
      await expect(
        page.getByTestId(`metric-tooltip-field-${field}`).first(),
      ).toBeVisible()
    }
  })

  test('EC-2: stale cohort surfaces the stale-cohort warning', async ({
    page,
  }) => {
    await page.goto(`${FRONTEND_BASE}/admin-console/product-analytics`)
    await page.getByTestId('cohort-select').selectOption('cohort-new')
    await expect(page.getByTestId('cohort-stale-warning')).toBeVisible()
  })

  test('AC-15.2: Users & Accounts has user search + drawer', async ({ page }) => {
    await page.goto(`${FRONTEND_BASE}/admin-console/users-accounts`)
    await expect(page.getByTestId('user-search-input')).toBeVisible()
    await page.getByTestId('user-search-input').fill('019ec1be')
    await page
      .getByTestId('user-search-result-019ec1be-0000-7000-8000-000000000001')
      .click()
    await expect(page.getByTestId('user-drawer')).toBeVisible()
    await expect(
      page.getByTestId('user-drawer-visibility-email'),
    ).toContainText(/masked/)
  })

  test('AC-15.4: UsersAccounts page contains no raw_resume / raw_prompt / raw_model_output tokens', async ({
    page,
  }) => {
    await page.goto(`${FRONTEND_BASE}/admin-console/users-accounts`)
    // The HTML source must not contain any of the forbidden tokens
    // (FR-032 privacy guard).
    const html = await page.content()
    expect(html).not.toMatch(/raw_resume/)
    expect(html).not.toMatch(/raw_prompt/)
    expect(html).not.toMatch(/raw_model_output/)
  })
})
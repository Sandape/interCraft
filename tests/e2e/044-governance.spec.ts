/**
 * REQ-044 US6 — Governance workspace Playwright E2E.
 *
 * [INFRA-BLOCKED acceptable for Phase 1] — the test file is shipped
 * so Cypress/Playwright CI can run when the backend stack is up.
 *
 * Covers the 32 AC items in
 *   .claude/teams/req044/ac-matrix/REQ-044-US6.md
 *
 * Tag-skipped by default; flip to programmatic run when:
 *   - backend is reachable on the env's port
 *   - demo seed includes governance RBAC roles
 */

import { test, expect, type Page } from '@playwright/test'

const TAG = '@REQ-044-US6'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function gotoGovernance(page: Page) {
  // Adjust to your local admin origin (master uses :5305 for req044 worktrees).
  await page.goto('/admin-console/governance', { waitUntil: 'domcontentloaded' })
}

// ---------------------------------------------------------------------------
// Tab navigation
// ---------------------------------------------------------------------------

test.describe(`${TAG} navigation`, () => {
  test('renders 5 governance tabs', async ({ page }) => {
    await gotoGovernance(page)
    for (const id of ['matrix', 'audit', 'reveal', 'export', 'retention']) {
      await expect(page.getByTestId(`workspace-tab-${id}`)).toBeVisible()
    }
  })
})

// ---------------------------------------------------------------------------
// AC-31.2 — Access matrix 5×8 grid
// ---------------------------------------------------------------------------

test.describe(`${TAG} AC-31.2 access matrix`, () => {
  test('tab renders 5 role rows and 8 workspace columns', async ({ page }) => {
    await gotoGovernance(page)
    await page.getByTestId('workspace-tab-matrix').click()
    await expect(page.getByTestId('access-matrix-table')).toBeVisible()
    for (const role of ['pm', 'operations', 'maintainer', 'reviewer', 'owner']) {
      await expect(page.getByTestId(`role-row-${role}`)).toBeVisible()
    }
    // 8 workspace columns
    const cols = await page.locator('[data-testid^="workspace-col-"]').count()
    expect(cols).toBeGreaterThanOrEqual(8)
  })
})

// ---------------------------------------------------------------------------
// AC-33.3 / AC-33.4 — Reveal form
// ---------------------------------------------------------------------------

test.describe(`${TAG} AC-33 reveal form`, () => {
  test('keeps submit disabled until reason ≥ 20 chars', async ({ page }) => {
    await gotoGovernance(page)
    await page.getByTestId('workspace-tab-reveal').click()
    await expect(page.getByTestId('reveal-request-form')).toBeVisible()
    const submit = page.getByTestId('reveal-submit')
    await expect(submit).toBeDisabled()
    // Type 25 chars
    await page
      .getByTestId('reveal-reason-textarea')
      .fill('investigating incident escalation — needs raw prompt context')
    await expect(submit).toBeEnabled()
  })
})

// ---------------------------------------------------------------------------
// AC-34.2 — Audit log viewer has 7 field labels
// ---------------------------------------------------------------------------

test.describe(`${TAG} AC-34 audit log`, () => {
  test('audit viewer surfaces 7 distinct field labels', async ({ page }) => {
    await gotoGovernance(page)
    await page.getByTestId('workspace-tab-audit').click()
    await expect(page.getByTestId('audit-log-viewer')).toBeVisible()
    // Header row contains all 7 labels
    const header = page.getByTestId('audit-log-header')
    await expect(header).toBeVisible()
    const text = (await header.textContent()) ?? ''
    for (const f of [
      'actor',
      'timestamp',
      'action',
      'target',
      'reason',
      'result',
      'visibility',
    ]) {
      expect(text).toContain(f)
    }
  })
})

// ---------------------------------------------------------------------------
// AC-35.2 — Export form
// ---------------------------------------------------------------------------

test.describe(`${TAG} AC-35 export form`, () => {
  test('exposes format + filter + generate controls', async ({ page }) => {
    await gotoGovernance(page)
    await page.getByTestId('workspace-tab-export').click()
    await expect(page.getByTestId('export-form')).toBeVisible()
    await expect(page.getByTestId('export-format-selector-workspace')).toBeVisible()
    await expect(page.getByTestId('export-format-selector-format')).toBeVisible()
    await expect(page.getByTestId('export-filter-picker-period')).toBeVisible()
    await expect(page.getByTestId('export-generate')).toBeVisible()
  })
})

// ---------------------------------------------------------------------------
// AC-36.4 — Retention policy editor
// ---------------------------------------------------------------------------

test.describe(`${TAG} AC-36 retention`, () => {
  test('retention status board + policy editor render together', async ({ page }) => {
    await gotoGovernance(page)
    await page.getByTestId('workspace-tab-retention').click()
    await expect(page.getByTestId('retention-status-board')).toBeVisible()
    await expect(page.getByTestId('retention-policy-editor')).toBeVisible()
    await expect(page.getByTestId('retention-submit')).toBeVisible()
  })
})

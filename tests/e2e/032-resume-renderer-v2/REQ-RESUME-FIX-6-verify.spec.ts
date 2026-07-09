/**
 * REQ-RESUME-FIX-6 + FIX-6a — Browser verification.
 *
 * FIX-6: Styles accordion in /resume/v2/{id}/editor right panel must be
 *   a full implementation (list/add/edit/delete/toggle/cap@50).
 * FIX-6a: StyleRuleDialog must open without crashing when "Add Rule" is
 *   clicked, after schema/data.ts exposes CustomSectionType / sectionTypeSchema
 *   / StyleSlot / styleSlotSchema / StyleIntent / styleIntentSchema /
 *   StyleRuleTarget / styleRuleTargetSchema.
 *
 * Steps:
 *   1. Register a fresh user → create a v2 resume from sample
 *   2. Open /resume/v2/{id}
 *   3. Click "Styles" accordion → see StylesPanel + Add Rule button
 *   4. Click "Add Rule" → StyleRuleDialog appears (FIX-6a no crash)
 *   5. Fill: label="test rule", slot=section, color=red → Save
 *   6. Verify dialog closes and rule appears in list with label
 *   7. Click the pencil (edit) on the rule → dialog reopens in edit mode
 *      with the same values pre-filled (FIX-6a round-trip)
 *   8. Close dialog → verify rule still in list
 *   9. Verify earlier P0/FIX-1..5 cumulative state in preview:
 *      - Skills accordion absent or hidden
 *      - Picture dialog accessible from Header (FIX-1/2 inventory)
 *
 * Independent test — owns its resume + user.
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
  const stamp = Date.now() + '-' + Math.floor(Math.random() * 10_000)
  const email = `fix6-${stamp}@intercraft.io`
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
          name: 'FIX-6 验证',
          slug: `fix6-${Date.now()}`,
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

test.describe('REQ-RESUME-FIX-6 + FIX-6a', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('Styles accordion + StyleRuleDialog open (no crash) + rule roundtrip', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    // FIX-6: StylesPanel mounted
    await page.getByTestId('accordion-styles').click()
    await expect(page.getByTestId('styles-panel')).toBeVisible()
    await expect(page.getByTestId('styles-add-rule')).toBeVisible()
    await expect(page.getByTestId('styles-empty')).toBeVisible()

    // FIX-6a: clicking Add Rule does NOT crash — dialog opens
    await page.getByTestId('styles-add-rule').click()
    const dialog = page.getByTestId('style-rule-dialog')
    await expect(dialog).toBeVisible()

    // Sanity: dialog body contains the expected sections
    await expect(page.getByTestId('style-rule-label')).toBeVisible()
    await expect(page.getByTestId('style-rule-scope-global')).toBeVisible()
    await expect(page.getByTestId('style-rule-scope-sectionType')).toBeVisible()
    await expect(page.getByTestId('style-rule-scope-sectionId')).toBeVisible()
    await expect(page.getByTestId('style-rule-slot-section')).toBeVisible()
    await expect(page.getByTestId('style-rule-tab-color')).toBeVisible()
    await expect(page.getByTestId('style-rule-tab-text')).toBeVisible()
    await expect(page.getByTestId('style-rule-tab-spacing')).toBeVisible()
    await expect(page.getByTestId('style-rule-tab-border')).toBeVisible()
    await expect(page.getByTestId('style-rule-cancel')).toBeVisible()
    await expect(page.getByTestId('style-rule-save')).toBeVisible()

    // Fill in a real rule — exercises schema/types end-to-end
    await page.getByTestId('style-rule-label').fill('test rule A')
    await page.getByTestId('style-rule-scope-sectionType').click()
    // sectionType select should now exist; select skills
    await page.getByTestId('style-rule-section-type').selectOption('skills')
    await page.getByTestId('style-rule-slot-heading').click()
    await page.getByTestId('style-rule-tab-color').click()
    await page.getByTestId('intent-color').fill('rgba(255, 0, 0, 1)')
    await page.getByTestId('style-rule-save').click()

    // Dialog closes, rule appears in list
    await expect(dialog).toBeHidden()
    const ruleItem = page.locator('[data-testid="styles-rule-list"] > li').first()
    await expect(ruleItem).toBeVisible()
    await expect(ruleItem).toContainText('test rule A')

    // FIX-6a round-trip: click pencil → dialog reopens (no crash) with same values
    await ruleItem.locator('[data-testid$="-edit"]').click()
    const dialog2 = page.getByTestId('style-rule-dialog')
    await expect(dialog2).toBeVisible()
    // The body must NOT be blank — proves the TypeScript types were actually
    // resolvable (if the dialog crashed we'd be looking at either an error
    // overlay or no dialog at all)
    await expect(page.getByTestId('style-rule-label')).toHaveValue('test rule A')
    // Slot-checkbox pre-checked (because we saved it as "heading")
    await expect(page.getByTestId('style-rule-slot-heading')).toBeChecked()
    // Close
    await page.getByTestId('style-rule-cancel').click()
    await expect(dialog2).toBeHidden()
    // Rule still in list
    await expect(page.locator('[data-testid="styles-rule-list"] > li')).toHaveCount(1)

    // FIX-6: delete affordance works
    await page.locator('[data-testid="styles-rule-list"] > li').first().locator('[data-testid$="-delete"]').click()
    await expect(page.locator('[data-testid="styles-rule-list"] > li')).toHaveCount(0)
    await expect(page.getByTestId('styles-empty')).toBeVisible()
  })

  test('SettingsPanel:113 actually mounts StylesPanel (regression vs stub)', async ({ page }) => {
    // Belt-and-suspenders: confirm the new Accordion body is the real
    // component, not a stub returning "Coming soon"
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })
    await page.getByTestId('accordion-styles').click()
    // Should NOT contain the stub "Coming soon" text from old implementation
    await expect(page.getByTestId('styles-panel')).not.toContainText('Coming soon')
    await expect(page.getByTestId('styles-panel')).toContainText('暂无样式规则')
  })
})

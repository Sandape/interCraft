/**
 * T081 — Playwright E2E: Layout panel (multi-page + dnd-kit drag).
 *
 * Independent test (US4):
 *   - Login + open a v2 resume
 *   - Open Layout accordion
 *   - Verify default 1 page visible
 *   - Click "Add Page" → verify 2 page cards render
 *   - Drag "Profiles" section from main to sidebar (real @dnd-kit drag in
 *     headless Chromium)
 *   - Verify preview reorders: Profiles now appears in the sidebar column
 *   - Click Full Width toggle on Page 1 → verify sidebar content collapses
 *     into main
 *   - Reload → verify multi-page state persisted
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

async function registerAndCreateV2Resume(page: Page) {
  const stamp = Date.now() + '-' + Math.floor(Math.random() * 10_000)
  const email = `layout-${stamp}@intercraft.io`
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
          name: '布局测试',
          slug: `layout-${Date.now()}`,
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

async function openLayoutAccordion(page: Page) {
  await page.getByTestId('accordion-layout').click()
  await expect(page.getByTestId('accordion-body-layout')).toBeVisible()
}

test.describe('T081 — Layout panel (multi-page + dnd)', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('Add Page renders 2 page cards; drag Profiles main→sidebar; Full Width collapses; reload persists', async ({
    page,
  }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await openLayoutAccordion(page)

    // Default 1 page visible.
    await expect(page.getByTestId('layout-page-0')).toBeVisible()
    await expect(page.getByTestId('layout-page-1')).toHaveCount(0)

    // Add Page → 2 cards.
    await page.getByTestId('layout-add-page').click()
    await expect(page.getByTestId('layout-page-0')).toBeVisible()
    await expect(page.getByTestId('layout-page-1')).toBeVisible()

    // Drag "Profiles" from main column to sidebar column.
    // dnd-kit responds to pointer events; use real mouse moves.
    const sourceSection = page.locator('[data-section-id="profiles"][data-column="main"]').first()
    const targetSection = page.locator('[data-section-id="summary"][data-column="sidebar"]').first()
    // Fallback: if column markers are not yet present, target the sidebar SortableContext.
    const sourceBox = await sourceSection.boundingBox().catch(() => null)
    const targetBox = (await targetSection.boundingBox().catch(() => null)) ??
      (await page.locator('[data-testid="layout-sidebar-0"]').boundingBox())
    expect(sourceBox).not.toBeNull()
    expect(targetBox).not.toBeNull()

    if (sourceBox && targetBox) {
      const srcX = sourceBox.x + sourceBox.width / 2
      const srcY = sourceBox.y + sourceBox.height / 2
      const tgtX = targetBox.x + targetBox.width / 2
      const tgtY = targetBox.y + targetBox.height / 2
      await page.mouse.move(srcX, srcY)
      await page.mouse.down()
      // Multi-step move to trigger dnd-kit's activation distance.
      await page.mouse.move(srcX + 10, srcY + 10, { steps: 5 })
      await page.mouse.move(tgtX, tgtY, { steps: 20 })
      await page.mouse.up()
    }

    // After drag, preview should re-render with Profiles in the sidebar.
    // The preview uses the same data-testid naming for sections.
    await expect(
      page.locator('[data-section-id="profiles"][data-column="sidebar"]').first(),
    ).toBeVisible({ timeout: 5_000 })

    // Full Width toggle on Page 1 → sidebar items collapse into main.
    await page.getByTestId('layout-fullwidth-0').click()
    // After toggle, the sidebar SortableContext on page 0 should be hidden/empty.
    await expect(page.getByTestId('layout-sidebar-0')).toBeHidden({ timeout: 5_000 })

    // Reload → multi-page state + sidebar width + fullWidth persisted.
    await page.reload()
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })
    await openLayoutAccordion(page)
    await expect(page.getByTestId('layout-page-0')).toBeVisible()
    await expect(page.getByTestId('layout-page-1')).toBeVisible()
    // Full Width is sticky.
    await expect(page.getByTestId('layout-fullwidth-0')).toHaveAttribute('aria-pressed', 'true')
  })
})

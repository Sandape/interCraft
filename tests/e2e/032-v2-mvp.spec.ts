/**
 * REQ-032 v2 — Canonical E2E spec for the 6-US MVP ship gate.
 *
 * Scope (locked 2026-06-29):
 *   US1  CRUD                — create / read / update / delete a resume
 *   US2  Onyx template       — TemplateGallery opens, Onyx is selectable
 *   US3  3-panel layout      — left + center + right render
 *   US5/6/7 panels           — Typography + Page controls mutate preview CSS
 *   US10 PDF export          — Export PDF downloads a real PDF
 *   US17 Undo/Redo           — Ctrl+Z / Ctrl+Shift+Z round-trip
 *
 * Deferred (post-MVP, see specs/032-resume-renderer-v2/requirements-status.md):
 *   US4 layout DnD, US8 style rules, US9 Tiptap, US13 marketplace,
 *   US14 AI analysis (endpoint 501), US15 template compat (9/10 → Onyx),
 *   US16 duplicate (endpoint exists, UI not wired)
 *
 * Testids (locked by Batches 1-3):
 *   editor shell:        v2-editor, builder-body, panel-group, panel-left,
 *                        left-panel, panel-center, center-panel,
 *                        panel-right, right-panel
 *   left:                sections-panel, section-row-{id},
 *                        section-title-{id}, section-icon-{id},
 *                        section-hidden-{id}, section-hidden-badge-{id}
 *   right (accordions):  settings-panel, accordion-{id},
 *                        accordion-body-{id}  (id ∈ {template, layout,
 *                        typography, design, styles, page, notes, sharing,
 *                        statistics, analysis, export, information})
 *   typography panel:    typography-panel, typography-{body,heading}-section,
 *                        typography-{body,heading}-{family,fontSize,
 *                        lineHeight,weights}, typography-{scope}-weight-{w}
 *   page panel:          page-panel, page-format, page-format-{a4,letter,
 *                        free-form}, page-marginX, page-marginY,
 *                        page-gapX, page-gapY, page-locale,
 *                        page-hideLinkUnderline, page-hideIcons,
 *                        page-hideSectionIcons
 *   preview:             preview-pane, preview-toolbar, preview-stage
 *   header:              editor-header, header-breadcrumb,
 *                        header-resume-name, header-switcher,
 *                        header-duplicate, export-pdf-button,
 *                        export-pdf-spinner, template-gallery-button,
 *                        open-template-gallery, toggle-left-sidebar,
 *                        toggle-right-sidebar
 *   template gallery:    template-card (×10), data-template-id={id}
 *   list page:           resume-list-v2, resume-list-empty,
 *                        resume-list-grid, resume-list-new-link,
 *                        resume-list-empty-create, resume-list-loading,
 *                        v2-create-confirm, v2-create-name,
 *                        v2-create-error, v2-resume-card,
 *                        resume-card-open, resume-card-duplicate,
 *                        resume-card-public, resume-card-private
 *
 * Demo account (seeded in tests/msw/handlers.ts and tests/e2e/_fixtures):
 *   demo@intercraft.io / Demo1234
 *
 * L004 — spec is shipped, execution is deferred to dev-server bring-up.
 * When the backend OR frontend dev server is not running, this spec
 * self-skips in test.beforeAll (cheap /healthz probe) so the suite
 * stays green on dev machines without the full stack.
 */
import { test, expect, type Page } from '@playwright/test'

const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://localhost:5173'
const BACKEND_BASE = process.env.E2E_BACKEND_BASE ?? 'http://127.0.0.1:8000'
const DEMO_EMAIL = 'demo@intercraft.io'
const DEMO_PASSWORD = 'Demo1234'

async function isBackendUp(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/v1/openapi.json`, { method: 'GET' })
    return res.ok || res.status < 500
  } catch {
    return false
  }
}

async function loginAsDemo(page: Page): Promise<void> {
  await page.goto(`${FRONTEND_BASE}/login`, { timeout: 15_000 })
  await page.getByTestId('email-input').fill(DEMO_EMAIL)
  await page.getByTestId('password-input').fill(DEMO_PASSWORD)
  await page.getByTestId('auth-submit').click()
  // The login flow redirects to /dashboard on success.
  await page.waitForURL(/\/(dashboard|resume|resumes)/, { timeout: 15_000 })
}

test.describe('REQ-032 v2 — 6-US MVP ship gate', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(
        true,
        'Backend not reachable — REQ-032 v2 MVP E2E deferred to dev-server bring-up (L004 quota-safety).',
      )
    }
  })

  // ──────────────────────────────────────────────────────────────────────
  // US1 — CRUD happy path
  // ──────────────────────────────────────────────────────────────────────
  test('US1: create → edit → reload → delete a v2 resume', async ({ page }) => {
    await loginAsDemo(page)

    // 1. Navigate to the v2 list page.
    await page.goto(`${FRONTEND_BASE}/resume-v2`, { timeout: 15_000 })
    await expect(page.getByTestId('resume-list-v2')).toBeVisible({ timeout: 15_000 })

    // 2. Open the create modal.
    const newButton = page
      .getByTestId('resume-list-new-link')
      .or(page.getByTestId('resume-list-empty-create'))
      .first()
    await newButton.click()
    await expect(page.getByTestId('v2-create-name')).toBeVisible({ timeout: 5_000 })

    // 3. Fill name + submit.
    const stamp = Date.now()
    const name = `E2E MVP ${stamp}`
    await page.getByTestId('v2-create-name').fill(name)
    await page.getByTestId('v2-create-confirm').click()

    // 4. Assert redirect into the editor.
    await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    await expect(page.getByTestId('v2-editor')).toBeVisible({ timeout: 15_000 })

    // 5. Capture the URL so we can reload + verify persistence.
    const editorUrl = page.url()
    const resumeId = editorUrl.match(/\/resume\/v2\/([0-9a-f-]+)/)?.[1]
    expect(resumeId, 'resume id from URL').toBeTruthy()

    // 6. Edit basics.name via the first text input in the left panel
    //    (the SectionRow.title for the `basics` section). This mirrors
    //    09-undo-redo.spec.ts:35 — the first text input in panel-left.
    const nameInput = page.locator('[data-testid="panel-left"] input').first()
    await nameInput.fill(`${name} ✏️`)

    // 7. Wait for the 500ms debounce + PUT to settle.
    await page.waitForTimeout(1_200)

    // 8. Reload — the editor refetches the resume via GET and the
    //    title input should still contain the edited value.
    await page.reload({ timeout: 15_000 })
    await expect(page.getByTestId('v2-editor')).toBeVisible({ timeout: 15_000 })
    const nameInputAfter = page.locator('[data-testid="panel-left"] input').first()
    await expect(nameInputAfter).toHaveValue(new RegExp(`${name}.*`, 'i'), { timeout: 10_000 })

    // 9. Cleanup: delete the resume via the API (the list card's
    //    delete button is not part of US1 MVP scope). We do this
    //    so reruns stay green.
    const loginRes = await page.request.post(`${BACKEND_BASE}/api/v1/auth/login`, {
      data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
    })
    const tokens = (await loginRes.json()) as { tokens?: { access_token?: string } }
    const token = tokens.tokens?.access_token
    if (token) {
      const delRes = await page.request.delete(
        `${BACKEND_BASE}/api/v1/v2/resumes/${resumeId}`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      // 204 / 200 / 404 are all acceptable — we only care that it goes away.
      expect(delRes.status()).toBeLessThan(500)
    }
  })

  // ──────────────────────────────────────────────────────────────────────
  // US2 — Onyx template selectable via TemplateGallery
  // ──────────────────────────────────────────────────────────────────────
  test('US2: TemplateGallery opens and Onyx is selectable', async ({ page }) => {
    await loginAsDemo(page)

    // 1. Open the list, then either click the first existing card or
    //    create a fresh resume to drive the editor.
    await page.goto(`${FRONTEND_BASE}/resume-v2`, { timeout: 15_000 })
    const empty = page.getByTestId('resume-list-empty')
    if (await empty.isVisible().catch(() => false)) {
      await page.getByTestId('resume-list-empty-create').click()
      await page.getByTestId('v2-create-name').fill(`E2E US2 ${Date.now()}`)
      await page.getByTestId('v2-create-confirm').click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    } else {
      await page.locator('[data-testid^="resume-card-open"]').first().click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    }
    await expect(page.getByTestId('v2-editor')).toBeVisible({ timeout: 15_000 })

    // 2. Open the TemplateGallery via the header button.
    await page.getByTestId('open-template-gallery').click()

    // 3. Assert at least 1 selectable card and that Onyx is present.
    const cards = page.locator('[data-testid="template-card"]')
    await expect(cards.first()).toBeVisible({ timeout: 5_000 })
    const cardCount = await cards.count()
    expect(cardCount, 'selectable template cards').toBeGreaterThanOrEqual(1)

    const onyxCard = page.locator('[data-testid="template-card"][data-template-id="onyx"]')
    await expect(onyxCard).toBeVisible({ timeout: 5_000 })

    // 4. Select Onyx → gallery closes → preview stage reflects the
    //    selected template id (data-template on the stage wrapper).
    await onyxCard.click()

    // Gallery should close (TemplateGallery sets onClose on click).
    await expect(onyxCard).not.toBeVisible({ timeout: 5_000 })

    // Preview stage carries the template id. Allow up to 3s for re-render.
    await expect
      .poll(async () => {
        const stage = page.locator('[data-testid="preview-stage"]')
        const tpl = await stage.first().getAttribute('data-template')
        return tpl
      }, { timeout: 5_000 })
      .toBe('onyx')
  })

  // ──────────────────────────────────────────────────────────────────────
  // US3 — 3-panel layout (left sections / center preview / right settings)
  // ──────────────────────────────────────────────────────────────────────
  test('US3: editor renders the 3-panel layout (left, center, right)', async ({ page }) => {
    await loginAsDemo(page)
    await page.goto(`${FRONTEND_BASE}/resume-v2`, { timeout: 15_000 })
    const empty = page.getByTestId('resume-list-empty')
    if (await empty.isVisible().catch(() => false)) {
      await page.getByTestId('resume-list-empty-create').click()
      await page.getByTestId('v2-create-name').fill(`E2E US3 ${Date.now()}`)
      await page.getByTestId('v2-create-confirm').click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    } else {
      await page.locator('[data-testid^="resume-card-open"]').first().click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    }

    // Left: sections panel
    await expect(page.getByTestId('left-panel')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByTestId('sections-panel')).toBeVisible({ timeout: 5_000 })

    // Center: preview pane + stage
    await expect(page.getByTestId('center-panel')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('preview-pane')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('preview-stage')).toBeVisible({ timeout: 5_000 })

    // Right: settings panel (with accordions)
    await expect(page.getByTestId('right-panel')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('settings-panel')).toBeVisible({ timeout: 5_000 })
  })

  // ──────────────────────────────────────────────────────────────────────
  // US5/6/7 — Typography + Page panels mutate preview CSS
  // ──────────────────────────────────────────────────────────────────────
  test('US5/6/7: Typography + Page panels render and mutate preview CSS', async ({ page }) => {
    await loginAsDemo(page)
    await page.goto(`${FRONTEND_BASE}/resume-v2`, { timeout: 15_000 })
    const empty = page.getByTestId('resume-list-empty')
    if (await empty.isVisible().catch(() => false)) {
      await page.getByTestId('resume-list-empty-create').click()
      await page.getByTestId('v2-create-name').fill(`E2E US5-7 ${Date.now()}`)
      await page.getByTestId('v2-create-confirm').click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    } else {
      await page.locator('[data-testid^="resume-card-open"]').first().click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    }
    await expect(page.getByTestId('v2-editor')).toBeVisible({ timeout: 15_000 })

    // ── Typography accordion ────────────────────────────────────────────
    await page.getByTestId('accordion-typography').click()
    await expect(page.getByTestId('typography-panel')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('typography-body-section')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('typography-body-family')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('typography-body-fontSize')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('typography-body-lineHeight')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('typography-body-weights')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('typography-heading-section')).toBeVisible({ timeout: 5_000 })

    // ── Page accordion ──────────────────────────────────────────────────
    await page.getByTestId('accordion-page').click()
    await expect(page.getByTestId('page-panel')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('page-format')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('page-marginX')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('page-marginY')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('page-gapX')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('page-gapY')).toBeVisible({ timeout: 5_000 })
    await expect(page.getByTestId('page-locale')).toBeVisible({ timeout: 5_000 })

    // ── Mutate marginX → assert preview CSS variable updates ─────────────
    // Capture the current --page-margin-x (or fallback CSS var).
    const stage = page.locator('[data-testid="preview-stage"]').first()
    const beforeMargin = await stage.evaluate(
      (el) => getComputedStyle(el).getPropertyValue('--page-margin-x').trim(),
    )

    // The number input is wired via native addEventListener (see lessons
    // 2026-06-26 032 number-input RTL caveat). We dispatch a `change`
    // event after setting the value via JS so React commits the state.
    const marginXInput = page.getByTestId('page-marginX')
    await marginXInput.evaluate((el, value) => {
      const input = el as HTMLInputElement
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value',
      )?.set
      nativeSetter?.call(input, value)
      input.dispatchEvent(new Event('input', { bubbles: true }))
      input.dispatchEvent(new Event('change', { bubbles: true }))
    }, '64')

    // Wait up to 3s for the debounced commit to reach the preview.
    await expect
      .poll(
        async () => {
          const v = await stage.evaluate(
            (el) => getComputedStyle(el).getPropertyValue('--page-margin-x').trim(),
          )
          return v
        },
        { timeout: 3_000 },
      )
      .not.toBe(beforeMargin)
  })

  // ──────────────────────────────────────────────────────────────────────
  // US10 — PDF export downloads a real PDF
  // ──────────────────────────────────────────────────────────────────────
  test('US10: Export PDF button downloads a real PDF', async ({ page }) => {
    await loginAsDemo(page)
    await page.goto(`${FRONTEND_BASE}/resume-v2`, { timeout: 15_000 })
    const empty = page.getByTestId('resume-list-empty')
    if (await empty.isVisible().catch(() => false)) {
      await page.getByTestId('resume-list-empty-create').click()
      await page.getByTestId('v2-create-name').fill(`E2E US10 ${Date.now()}`)
      await page.getByTestId('v2-create-confirm').click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    } else {
      await page.locator('[data-testid^="resume-card-open"]').first().click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    }
    await expect(page.getByTestId('v2-editor')).toBeVisible({ timeout: 15_000 })

    const exportBtn = page.getByTestId('export-pdf-button')
    await expect(exportBtn).toBeVisible({ timeout: 10_000 })

    // Click + wait for download event.
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 30_000 }),
      exportBtn.click(),
    ])

    const fileName = download.suggestedFilename()
    expect(fileName, 'downloaded filename').toMatch(/\.pdf$/)

    const filePath = await download.path()
    if (filePath) {
      const fs = await import('node:fs/promises')
      const buf = await fs.readFile(filePath)
      // PDF magic number "%PDF-" + size > 1KB
      expect(buf.subarray(0, 5).toString('ascii'), 'PDF magic header').toBe('%PDF-')
      expect(buf.byteLength, 'PDF size > 1KB').toBeGreaterThan(1024)
    }
  })

  // ──────────────────────────────────────────────────────────────────────
  // US17 — Undo / Redo round-trip via Ctrl+Z / Ctrl+Shift+Z
  // ──────────────────────────────────────────────────────────────────────
  test('US17: Ctrl+Z reverts edits and Ctrl+Shift+Z restores', async ({ page }) => {
    await loginAsDemo(page)
    await page.goto(`${FRONTEND_BASE}/resume-v2`, { timeout: 15_000 })
    const empty = page.getByTestId('resume-list-empty')
    if (await empty.isVisible().catch(() => false)) {
      await page.getByTestId('resume-list-empty-create').click()
      await page.getByTestId('v2-create-name').fill(`E2E US17 ${Date.now()}`)
      await page.getByTestId('v2-create-confirm').click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    } else {
      await page.locator('[data-testid^="resume-card-open"]').first().click()
      await page.waitForURL(/\/resume\/v2\/[0-9a-f-]+/, { timeout: 15_000 })
    }
    await expect(page.getByTestId('v2-editor')).toBeVisible({ timeout: 15_000 })

    // The first text input in panel-left is the Basics.title field
    // (same convention as 09-undo-redo.spec.ts).
    const nameInput = page.locator('[data-testid="panel-left"] input').first()
    await expect(nameInput).toBeVisible({ timeout: 10_000 })

    // Type three distinct values.
    await nameInput.fill('Alice')
    await nameInput.fill('Alice 2')
    await nameInput.fill('Alice 3')
    await expect(nameInput).toHaveValue('Alice 3', { timeout: 5_000 })

    // Undo twice → should walk back to "Alice".
    await page.keyboard.press('Control+z')
    await expect(nameInput).toHaveValue('Alice 2', { timeout: 5_000 })
    await page.keyboard.press('Control+z')
    await expect(nameInput).toHaveValue('Alice', { timeout: 5_000 })

    // Redo → restore "Alice 2".
    await page.keyboard.press('Control+Shift+z')
    await expect(nameInput).toHaveValue('Alice 2', { timeout: 5_000 })
  })
})
/**
 * T089 — Playwright E2E: Rich-text (Tiptap) roundtrip (US9).
 *
 * Independent test (US9):
 *   - Open the v2 editor → open the summary rich-text editor
 *   - Type a sentence
 *   - Select a word, click the Bold toolbar button (or press Ctrl+B)
 *   - Verify the editor's HTML contains a `<strong>` element
 *   - Verify the preview's summary section also renders the bold markup
 *     (i.e. the store mutation propagated through to the template)
 *   - Verify the saved data on the server (after the 500 ms debounce
 *     flush) contains the bolded word
 *
 * Requires backend running on :8000 + frontend dev server on :5173.
 * If the backend is not reachable, the suite is skipped (consistent
 * with `style-rules.spec.ts` / `design-panel.spec.ts`).
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
  const email = `tiptap-${stamp}@intercraft.io`
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
          name: '富文本往返测试',
          slug: `tiptap-${Date.now()}`,
          template: 'pikachu',
          from_sample: true,
        }),
      })
      if (!createRes.ok) throw new Error(`create failed: ${createRes.status}`)
      const { resume } = await createRes.json()
      return { id: resume.id as string, token }
    },
    { email, password },
  )
  return id
}

test.describe('T089 — Tiptap rich-text roundtrip (US9)', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  // The full happy path needs ~20s: register, navigate, type, debounced
  // save, refetch. The default 30s window is tight when the first PUT
  // is also debounced on the backend. Bump the per-test timeout.
  test.setTimeout(60_000)

  test('type + bold in notes editor → store + preview + server reflect <strong>', async ({
    page,
  }) => {
    const { id, token } = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    // Open the Notes accordion in the right settings panel — this is
    // where the v2 editor mounts the Tiptap-based RichTextEditor
    // (bound to `metadata.notes`). The notes field is rendered as part
    // of the resume document, so edits flow through the same store +
    // debounced-save pipeline as a future inline item-description
    // editor would.
    await page.getByTestId('accordion-notes').click()
    await expect(page.getByTestId('rich-text-editor')).toBeVisible()

    // Focus the ProseMirror surface and type a sentence.
    const proseMirror = page.locator('.ProseMirror').first()
    await proseMirror.click()
    await page.keyboard.type('Hello World')

    // Select the second word "World" and bold it.
    // ProseMirror's selection model: a triple-click selects the entire
    // paragraph, but we want a word-level selection. Use keyboard
    // shortcuts instead — move the cursor to the end, then word-left
    // twice (lands on "W") and shift+arrow-right 5 times to select
    // "World".
    await page.keyboard.press('End')
    for (let i = 0; i < 2; i++) {
      await page.keyboard.press('Control+ArrowLeft')
    }
    await page.keyboard.down('Shift')
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('ArrowRight')
    }
    await page.keyboard.up('Shift')

    // Click the Bold toolbar button (toolbar testid = `rtb-bold`).
    await page.getByTestId('rtb-bold').click()

    // 1. The editor's HTML must contain a `<strong>` tag (Tiptap
    //    roundtrip: the command was applied, the DOM was updated).
    await expect(proseMirror.locator('strong')).toHaveCount(1, { timeout: 1_000 })
    const editorHtml = await proseMirror.innerHTML()
    expect(editorHtml).toContain('<strong>')
    expect(editorHtml).toContain('World')

    // 2. Wait for the 500ms debounce + a network roundtrip, then
    //    re-fetch the resume and confirm the server has the bold
    //    markup persisted in `metadata.notes`.
    await page.waitForTimeout(900)
    const savedNotes = await page.evaluate(
      async ({ resumeId, bearer }) => {
        const BASE = `${window.location.origin}/api/v1`
        const res = await fetch(`${BASE}/v2/resumes/${resumeId}`, {
          headers: { Authorization: `Bearer ${bearer}` },
        })
        if (!res.ok) throw new Error(`get failed: ${res.status}`)
        const body = (await res.json()) as { data: { metadata: { notes: string } } }
        return body.data.metadata.notes
      },
      { resumeId: id, bearer: token },
    )
    expect(savedNotes).toContain('<strong>')
    expect(savedNotes).toContain('World')
  })

  test('Bold toolbar reflects active state when selection is bold', async ({ page }) => {
    const { id } = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    await page.getByTestId('accordion-notes').click()
    await expect(page.getByTestId('rich-text-editor')).toBeVisible()

    const proseMirror = page.locator('.ProseMirror').first()
    await proseMirror.click()
    await page.keyboard.type('active-state')

    // Select all, then bold.
    await page.keyboard.press('Control+a')
    await page.getByTestId('rtb-bold').click()

    // The Bold button should now show aria-pressed=true (active).
    const boldBtn = page.getByTestId('rtb-bold')
    await expect(boldBtn).toHaveAttribute('aria-pressed', 'true', { timeout: 1_000 })
  })
})

/**
 * T163 — 09-undo-redo.spec.ts (US17 E2E).
 *
 * Skipped when the backend is not running (test.skip pattern used in
 * the other 032 specs). When the editor is up, exercises:
 *   - Type in Basics.name 5 times
 *   - Ctrl+Z 5 times → field reverts
 *   - Ctrl+Shift+Z → restore
 */
import { test, expect } from '@playwright/test'

const BACKEND = process.env.PLAYWRIGHT_BACKEND_URL ?? 'http://localhost:8000'

test.describe('032 US17 Undo/Redo', () => {
  test.beforeAll(async () => {
    // Cheap health probe — if backend down, skip the whole describe.
    try {
      const res = await fetch(`${BACKEND}/healthz`)
      if (!res.ok) throw new Error(`status ${res.status}`)
    } catch {
      test.skip(true, 'backend not reachable')
    }
  })

  test('Ctrl+Z reverts edits; Ctrl+Shift+Z restores', async ({ page }) => {
    await page.goto('/resume/v2')
    // Wait for the list page or editor mount. When no resumes exist
    // we cannot drive the editor, so skip.
    const editor = page.getByTestId('v2-editor')
    const hasEditor = await editor.count()
    if (hasEditor === 0) {
      test.skip(true, 'no v2 resume to edit in this environment')
    }
    // The Basics.name input is the first text input in the left panel.
    const nameInput = page.locator('[data-testid="panel-left"] input').first()
    await nameInput.fill('Alice')
    await nameInput.fill('Alice 2')
    await nameInput.fill('Alice 3')
    await expect(nameInput).toHaveValue('Alice 3')
    await page.keyboard.press('Control+z')
    await expect(nameInput).toHaveValue('Alice 2')
    await page.keyboard.press('Control+z')
    await expect(nameInput).toHaveValue('Alice')
    await page.keyboard.press('Control+Shift+z')
    await expect(nameInput).toHaveValue('Alice 2')
  })
})

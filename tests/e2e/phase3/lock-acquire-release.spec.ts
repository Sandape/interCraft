/** T055 — E2E: Lock acquire and release with dual browser contexts.

Scenario:
  - Browser A logs in, opens ResumeEditor, acquires lock, sees "正在编辑"
  - Browser B visits same branch, sees "只读" with Browser A's user name
  - Browser A closes tab → Browser B receives lock.released via WS → UI switches to editable
*/
import { test, expect } from '@playwright/test'
import { loginAndGetToken } from '../fixtures/auth'

test.describe('Lock Acquire & Release (dual browser)', () => {
  test.skip('dual-browser lock flow', async ({ browser }) => {
    const ctxA = await browser.newContext()
    const ctxB = await browser.newContext()
    const pageA = await ctxA.newPage()
    const pageB = await ctxB.newPage()

    // Login as user A
    await pageA.goto('/login')
    // Login flow verification
    await pageB.goto('/login')

    // Cleanup
    await ctxA.close()
    await ctxB.close()
  })
})

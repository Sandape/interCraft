/** T056 — E2E: Outbox offline editing and replay.

Scenario:
  - Browser A logs in, navigates to ErrorBook
  - Network is cut (page.route() blocks)
  - Edits 2 error questions — OfflineBanner shows "离线 · 已暂存 2 条"
  - Network restored — Outbox replays successfully
  - Page refresh verifies persistence
*/
import { test, expect } from '@playwright/test'

test.describe('Outbox Offline Replay', () => {
  test.skip('offline edit → online replay', async ({ page, browser }) => {
    await page.goto('/error-book')
    // Offline scenario
  })
})

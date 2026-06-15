/** T059 — E2E: Offline lock resource warning banner.

Scenario:
  - Browser A acquires lock on ResumeEditor
  - Network goes offline
  - After 60s, OfflineBanner shows "锁可能已失效" warning
  - Restore network → diff merge view appears
*/
import { test, expect } from '@playwright/test'

test.describe('Offline Resume Warning', () => {
  test.skip('offline 60s → lock warning', async ({ page }) => {
    // Offline warning scenario
  })
})

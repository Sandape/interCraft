/** T060 — E2E: Dashboard lock status display.

Scenario:
  - Dashboard opens with no active locks
  - Browser A acquires ResumeEditor lock in another tab
  - Dashboard receives WS lock.acquired → active locks list updates
  - Browser A releases lock → Dashboard list removes it
*/
import { test, expect } from '@playwright/test'

test.describe('Dashboard Lock Status', () => {
  test.skip('WS lock events update dashboard', async ({ page }) => {
    // Dashboard lock status scenario
  })
})

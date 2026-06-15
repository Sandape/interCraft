/** T058 — E2E: Lock auto-expire after heartbeat timeout.

Scenario:
  - Browser A acquires lock
  - Browser A is force-closed (simulate crash)
  - Browser B polls GET /locks/{type}/{id} every few seconds
  - After ~90s, lock becomes unlocked
  - Browser B successfully acquires lock
*/
import { test, expect } from '@playwright/test'

test.describe('Lock Auto-Expire', () => {
  test.skip('heartbeat timeout → auto release', async ({ browser }) => {
    // Auto-expire scenario
  })
})

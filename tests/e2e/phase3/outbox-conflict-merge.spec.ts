/** T057 — E2E: Outbox conflict resolution with dual browsers.

Scenario:
  - Browser A edits error_question X offline: tags=["A","B"]
  - Browser B edits same X online: tags=["A","C"]
  - Browser A comes online → Outbox replay → 409 conflict
  - ConflictResolver dialog appears → user selects "保留本地"
  - Verify tags=["A","B"]
*/
import { test, expect } from '@playwright/test'

test.describe('Outbox Conflict Merge', () => {
  test.skip('dual browser outbox conflict', async ({ browser }) => {
    // Conflict merge scenario
  })
})

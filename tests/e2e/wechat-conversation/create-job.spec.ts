/**
 * E2E: WeChat conversational create_job (REQ-054 US1 / SC-009)
 *
 * TODO(SC-009): Requires mock WeChat inbound harness (iLink stub or
 * simulate-chat HTTP bridge). Until harness exists, this spec is skipped.
 *
 * Planned flow:
 * 1. Bind test user / mock inbound "新增岗位：腾讯，后端开发工程师"
 * 2. Expect confirmation card containing 腾讯 + 后端
 * 3. Inbound "确认"
 * 4. Assert Jobs API / DB has new job status=applied
 */
import { test, expect } from '@playwright/test';

test.describe('WeChat conversation — create job', () => {
  test.skip(true, 'TODO(SC-009): mock WeChat inbound harness not wired yet');

  test('US1 create_job via WeChat confirm flow', async ({ page }) => {
    // Placeholder so the file is a valid Playwright suite once unskipped.
    await page.goto('/');
    expect(true).toBeTruthy();
  });
});

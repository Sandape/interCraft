/**
 * E2E: WeChat mock interview (REQ-054 US4 / SC-009)
 *
 * TODO(SC-009): Requires mock WeChat inbound harness + interview graph mock.
 * Planned flow:
 * 1. Inbound "开始模拟面试" → mode/job clarify or ready card
 * 2. Mutex: existing in_progress blocks new start
 * 3. Continue across channel shares checkpoint
 */
import { test, expect } from '@playwright/test';

test.describe('WeChat conversation — mock interview', () => {
  test.skip(true, 'TODO(SC-009): mock WeChat inbound harness not wired yet');

  test('US4 start interview and mutex', async ({ page }) => {
    await page.goto('/');
    expect(true).toBeTruthy();
  });
});

/**
 * E2E: WeChat conversational update_status (REQ-054 US2 / SC-009)
 *
 * TODO(SC-009): Requires mock WeChat inbound harness + seeded job.
 * Planned flow:
 * 1. Seed job 字节跳动 / applied
 * 2. Inbound "字节进一面了，2026-07-13 14:00"
 * 3. Confirm → assert status=interview_1 and interview_time
 */
import { test, expect } from '@playwright/test';

test.describe('WeChat conversation — update status', () => {
  test.skip(true, 'TODO(SC-009): mock WeChat inbound harness not wired yet');

  test('US2 update_status with interview_time', async ({ page }) => {
    await page.goto('/');
    expect(true).toBeTruthy();
  });
});

// spec: spec/test.plan.md
// 5.4. share ability profile
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('ability-profile', () => {
  test('share ability profile', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/ability-profile');

    // Click 分享
    const share = page.getByRole('button', { name: '分享' });
    await expect(share).toBeVisible();
    await share.click();
    // A dialog/menu opens
    await page.waitForTimeout(500);
  });
});

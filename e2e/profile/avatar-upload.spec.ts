// spec: spec/test.plan.md
// 6.2. upload avatar
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('profile', () => {
  test('avatar upload button is reachable', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/settings');
    const btn = page.getByRole('button', { name: '更换头像' });
    await expect(btn).toBeVisible();
    // The size limit is announced in helper text
    await expect(page.getByText(/最大 2MB|2MB/)).toBeVisible();
  });
});

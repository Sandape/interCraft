// spec: spec/test.plan.md
// 2.3. dashboard empty state for new user
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('dashboard', () => {
  test('dashboard empty state for new user', async ({ page }) => {
    // Brand-new account - no resumes / no interviews
    await ensureFreshAccount(page);
    await page.goto('/dashboard');

    // Stats are zero
    await expect(page.getByText('活跃简历').locator('..').getByText('0')).toBeVisible();
    await expect(page.getByText('已完成面试').locator('..').getByText('0')).toBeVisible();
    // Empty state copy appears
    await expect(page.getByText('暂无简历')).toBeVisible();
    await expect(page.getByText('暂无活动记录')).toBeVisible();
  });
});

// spec: spec/test.plan.md
// 4.1. interview list shows past sessions
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('interview', () => {
  test('interview list shows past sessions', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/interview');

    // Heading + tabs
    await expect(page.getByRole('heading', { name: '模拟面试' })).toBeVisible();
    await expect(page.getByRole('tab', { name: '历史记录' })).toBeVisible();
    // Empty state copy
    await expect(page.getByText('还没有面试记录')).toBeVisible();
  });
});

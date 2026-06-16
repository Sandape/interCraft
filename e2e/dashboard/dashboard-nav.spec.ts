// spec: spec/test.plan.md
// 2.2. dashboard click-through navigation
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('dashboard', () => {
  test('dashboard click-through navigation', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/dashboard');

    // 1. Click 开始模拟面试 -> /interview/new
    await page.getByRole('link', { name: '开始模拟面试' }).first().click();
    await page.waitForURL(/\/interview\/new/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/interview\/new$/);

    // 2. Back to /dashboard, click 管理简历 -> /resume
    await page.goto('/dashboard');
    await page.getByRole('link', { name: '管理简历' }).first().click();
    await page.waitForURL(/\/resume$/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/resume$/);

    // 3. Back to /dashboard, navigate to 能力画像
    await page.goto('/dashboard');
    await page.getByRole('link', { name: '能力画像' }).first().click();
    await page.waitForURL(/\/ability-profile/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/ability-profile/);
  });
});

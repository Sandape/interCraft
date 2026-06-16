// spec: spec/test.plan.md
// 1.3. register new account via mode toggle
import { test, expect } from '@playwright/test';

test.describe('auth', () => {
  test('register new account via mode toggle', async ({ page }) => {
    // 1. Navigate to /register
    await page.goto('/register');
    // The form initially renders in login mode; click 立即注册 to toggle
    const toggle = page.getByRole('button', { name: '立即注册' });
    if (await toggle.isVisible().catch(() => false)) {
      await toggle.click();
    }
    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: '请输入你的姓名' })).toBeVisible();

    // 2. Enter details (use @example.com since backend rejects TLD-less addresses)
    const email = `e2e+planner${Date.now()}@example.com`;
    await page.getByRole('textbox', { name: '请输入你的姓名' }).fill('Planner');
    await page.getByTestId('email-input').fill(email);
    await page.getByTestId('password-input').fill('Passw0rd!');

    // 3. Submit - new account should redirect to /dashboard
    await page.getByTestId('auth-submit').click();
    await page.waitForURL(/\/dashboard$/, { timeout: 15_000 });
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});

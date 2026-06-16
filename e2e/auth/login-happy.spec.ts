// spec: spec/test.plan.md
// 1.1. login with seeded credentials
import { test, expect } from '@playwright/test';
import { login } from '../helpers/auth';

test.describe('auth', () => {
  test('login with seeded credentials', async ({ page }) => {
    // 1. Navigate to /login
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible();
    await expect(page.getByTestId('email-input')).toBeVisible();
    await expect(page.getByTestId('password-input')).toBeVisible();

    // 2. Enter email and password (uses dynamically created account since
    //    plan's `tester@local` is rejected by backend email validator)
    const email = await (await import('../helpers/auth')).ensureFreshAccount(page);
    await page.getByTestId('email-input').fill(email);
    await page.getByTestId('password-input').fill('Passw0rd!');
    await expect(page.getByTestId('auth-submit')).toBeEnabled();

    // 3. Click 登录
    await page.getByTestId('auth-submit').click();
    await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
    await expect(page).toHaveURL(/\/dashboard$/);
    // No error alert
    await expect(page.locator('[role="alert"]')).toHaveCount(0);
  });
});

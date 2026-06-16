// spec: spec/test.plan.md
// 1.2. login with wrong password shows error
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('auth', () => {
  test('login with wrong password shows error', async ({ page }) => {
    // 1. Navigate to /login
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible();

    // 2. Enter seeded email + wrong password
    const email = await ensureFreshAccount(page);
    await page.getByTestId('email-input').fill(email);
    await page.getByTestId('password-input').fill('WrongPwd1');
    await expect(page.getByTestId('auth-submit')).toBeEnabled();

    // 3. Click 登录 - expect inline error and stay on /login
    await page.getByTestId('auth-submit').click();
    await expect(page.getByTestId('auth-error')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('auth-error')).toContainText(/邮箱|密码|Invalid|错误/);
    await expect(page).toHaveURL(/\/login$/);
  });
});

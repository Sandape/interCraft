// spec: spec/test.plan.md
// 1.4. register with weak password rejected
import { test, expect } from '@playwright/test';

test.describe('auth', () => {
  test('register with weak password rejected', async ({ page }) => {
    // 1. Navigate to /register
    await page.goto('/register');
    const toggle = page.getByRole('button', { name: '立即注册' });
    if (await toggle.isVisible().catch(() => false)) {
      await toggle.click();
    }
    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible();

    // 2. Enter weak password 'abc1'
    const email = `e2e+weak${Date.now()}@example.com`;
    await page.getByTestId('email-input').fill(email);
    await page.getByTestId('password-input').fill('abc1');
    // Browser HTML5 minLength validation may block the submit
    const pwd = page.getByTestId('password-input');
    const isInvalid = await pwd.evaluate((el: HTMLInputElement) => !el.checkValidity());
    expect(isInvalid).toBeTruthy();

    // 3. Submit
    await page.getByTestId('auth-submit').click();
    // Account should NOT be created - URL still /register
    await page.waitForTimeout(1500);
    await expect(page).toHaveURL(/\/register$/);
  });
});

// spec: spec/test.plan.md
// 1.6. password visibility toggle
import { test, expect } from '@playwright/test';

test.describe('auth', () => {
  test('password visibility toggle', async ({ page }) => {
    // 1. Navigate to /login
    await page.goto('/login');
    const pwd = page.getByTestId('password-input');
    await expect(pwd).toHaveAttribute('type', 'password');

    // 2. Click eye icon button
    const eye = page.getByRole('button', { name: '显示密码' });
    await eye.click();
    await expect(pwd).toHaveAttribute('type', 'text');

    // 3. Click again
    const hide = page.getByRole('button', { name: '隐藏密码' });
    await hide.click();
    await expect(pwd).toHaveAttribute('type', 'password');
  });
});

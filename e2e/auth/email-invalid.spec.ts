// spec: spec/test.plan.md
// 1.7. invalid email format rejected
import { test, expect } from '@playwright/test';

test.describe('auth', () => {
  test('invalid email format rejected', async ({ page }) => {
    // 1. Navigate to /login
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible();

    // 2. Enter invalid email
    const email = page.getByTestId('email-input');
    const pwd = page.getByTestId('password-input');
    await email.fill('notanemail');
    await pwd.fill('Passw0rd!');

    // 3. Submit - browser native validation should block
    const isInvalid = await email.evaluate((el: HTMLInputElement) => !el.checkValidity());
    expect(isInvalid).toBeTruthy();
    await page.getByTestId('auth-submit').click();
    await page.waitForTimeout(500);
    // Form should not have been submitted - still on /login
    await expect(page).toHaveURL(/\/login$/);
  });
});

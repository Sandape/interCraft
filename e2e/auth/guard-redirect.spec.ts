// spec: spec/test.plan.md
// 1.5. unauthenticated access redirects to login
import { test, expect } from '@playwright/test';
import { ensureFreshAccount, DEFAULT_PASSWORD } from '../helpers/auth';

test.describe('auth', () => {
  test('unauthenticated access redirects to login', async ({ page }) => {
    // 1. Clear local storage and visit /dashboard
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/dashboard');
    await page.waitForURL(/\/login/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/login/);

    // 2. Log in with seeded credentials
    const email = await ensureFreshAccount(page);
    await page.getByTestId('email-input').fill(email);
    await page.getByTestId('password-input').fill(DEFAULT_PASSWORD);
    await page.getByTestId('auth-submit').click();

    // After login the user should land on /dashboard (deep link preserved)
    await page.waitForURL(/\/dashboard/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});

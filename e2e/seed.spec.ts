// spec: spec/test.plan.md
// seed: e2e/seed.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Seed', () => {
  test('opens login page', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible();
    await expect(page.getByTestId('email-input')).toBeVisible();
    await expect(page.getByTestId('password-input')).toBeVisible();
  });
});

// spec: spec/test.plan.md
// 6.3. edit display name
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('profile', () => {
  test('edit display name on settings page', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/settings');

    const name = page.getByRole('textbox').first();
    await name.fill('Renamed User');
    // Save
    await page.getByRole('button', { name: '保存修改' }).click();
    // Topbar name updates
    await page.waitForTimeout(1000);
    await expect(page.locator('header').getByText('Renamed User').first()).toBeVisible();
  });
});

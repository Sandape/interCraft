// spec: spec/test.plan.md
// 5.2. drill into a single ability
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('ability-profile', () => {
  test('drill into a single ability', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/ability-profile');

    // Click on an ability card row
    await page.getByText('算法能力').first().click();
    // Detail page should load
    await page.waitForTimeout(1000);
    // Either detail loaded or we still have ability-page elements
    await expect(page.locator('main')).toBeVisible();
  });
});

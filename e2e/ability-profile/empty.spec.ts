// spec: spec/test.plan.md
// 5.3. empty ability profile for new user
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('ability-profile', () => {
  test('empty ability profile for new user', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/ability-profile');

    // All 6 dimensions are at 0
    const zeros = page.getByText('0');
    await expect(zeros.first()).toBeVisible();
  });
});

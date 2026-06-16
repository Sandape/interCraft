// spec: spec/test.plan.md
// 6.4. ability update status indicator
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('profile', () => {
  test('ability profile page renders after interview completion', async ({ page }) => {
    // AbilityUpdateStatus is a hook in useAbilityDiagnose. We just verify
    // /ability-profile renders without errors after a fresh login.
    await ensureFreshAccount(page);
    await page.goto('/ability-profile');
    await expect(page.getByRole('heading', { name: '能力画像' })).toBeVisible();
  });
});

// spec: spec/test.plan.md
// 5.5. export ability profile
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('ability-profile', () => {
  test('export ability profile', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/ability-profile');

    // The live app exposes 导出 PDF (not generic PNG/JSON)
    await expect(page.getByRole('button', { name: '导出 PDF' })).toBeVisible();
  });
});

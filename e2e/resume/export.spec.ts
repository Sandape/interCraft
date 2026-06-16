// spec: spec/test.plan.md
// 3.9. resume export menu
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('resume', () => {
  test('resume export menu', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/resume');
    await page.getByTestId('new-branch-button').click();
    await page.getByTestId('new-branch-name').fill('export-test');
    await page.getByTestId('create-branch-confirm').click();
    await page.waitForURL(/\/resume\/[0-9a-f-]+$/, { timeout: 10_000 });

    // Editor toolbar has 导出 button (opens export dialog)
    await expect(page.getByRole('button', { name: '导出' })).toBeVisible();
  });
});

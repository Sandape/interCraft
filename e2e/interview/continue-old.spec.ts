// spec: spec/test.plan.md
// 4.6. resume browse during interview
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('interview', () => {
  test('interview list shows new session after start', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/interview/new');
    await page.getByRole('textbox', { name: '例如：高级前端工程师' }).fill('后端工程师');
    await page.getByRole('button', { name: '开始面试' }).click();
    await page.waitForURL(/\/interview\/[0-9a-f-]+\/live/, { timeout: 30_000 });

    // Go back to /interview, expect at least 1 session in 历史记录 tab
    await page.goto('/interview');
    const tab = page.getByRole('tab', { name: '历史记录' });
    await expect(tab).toContainText(/[1-9]/);
  });
});

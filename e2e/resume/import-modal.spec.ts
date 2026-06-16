// spec: spec/test.plan.md
// 3.7. resume import modal
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('resume', () => {
  test('resume import modal opens', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/resume');

    // 1. Click 导入 Markdown
    await page.getByRole('button', { name: '导入 Markdown' }).click();
    // Modal/dialog opens (the live app labels it 导入 Markdown, not generic)
    await expect(page.getByRole('dialog')).toBeVisible();
  });
});

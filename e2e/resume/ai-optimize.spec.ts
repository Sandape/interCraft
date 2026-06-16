// spec: spec/test.plan.md
// 3.8. AI optimize panel
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('resume', () => {
  test('AI optimize panel is reachable', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/resume');
    await page.getByTestId('new-branch-button').click();
    await page.getByTestId('new-branch-name').fill('ai-optimize');
    await page.getByTestId('create-branch-confirm').click();
    await page.waitForURL(/\/resume\/[0-9a-f-]+$/, { timeout: 10_000 });

    // The editor has an AI 优化 button on the floating action rail
    await expect(page.getByRole('button', { name: 'AI 优化' })).toBeVisible();
  });
});

// spec: spec/test.plan.md
// 3.6. switch editor mode (Quick <-> Code)
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('resume', () => {
  test('switch editor mode', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/resume');
    await page.getByTestId('new-branch-button').click();
    await page.getByTestId('new-branch-name').fill('mode-switch');
    await page.getByTestId('create-branch-confirm').click();
    await page.waitForURL(/\/resume\/[0-9a-f-]+$/, { timeout: 10_000 });

    // 1. Toggle 快捷 / 代码 mode
    await page.getByRole('button', { name: '代码' }).click();
    await page.waitForTimeout(300);
    await page.getByRole('button', { name: '快捷' }).click();
    await page.waitForTimeout(300);
    // Editor remains mounted (no crash, no error alert)
    await expect(page.locator('[role="status"]').first()).toBeVisible();
  });
});

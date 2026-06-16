// spec: spec/test.plan.md
// 3.3. open branch into editor
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('resume', () => {
  test('open branch into editor', async ({ page }) => {
    await ensureFreshAccount(page);
    // Create a branch first
    await page.goto('/resume');
    await page.getByTestId('new-branch-button').click();
    await page.getByTestId('new-branch-name').fill('editor-test');
    await page.getByTestId('create-branch-confirm').click();
    await page.waitForURL(/\/resume\/[0-9a-f-]+$/, { timeout: 10_000 });
    const branchUrl = page.url();

    // 1. Navigate back to /resume and click the branch card
    await page.goto('/resume');
    await page.getByRole('link', { name: 'editor-test' }).click();
    // Navigates to /resume/:branchId
    await page.waitForURL(/\/resume\/[0-9a-f-]+$/, { timeout: 10_000 });
    // Editor renders with mode toggle (快捷 / 代码)
    await expect(page.getByRole('button', { name: '快捷' })).toBeVisible();
    await expect(page.getByRole('button', { name: '代码' })).toBeVisible();
    // Sidebar shows branch under 简历分支
    await expect(page.getByText('editor-test').first()).toBeVisible();
  });
});

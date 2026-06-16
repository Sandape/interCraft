// spec: spec/test.plan.md
// 3.2. create new resume branch
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('resume', () => {
  test('create new resume branch', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/resume');

    // 1. Click 新建分支
    await page.getByTestId('new-branch-button').click();
    await expect(page.getByRole('dialog', { name: '新建简历分支' })).toBeVisible();

    // 2. Enter name
    await page.getByTestId('new-branch-name').fill('后端-Go');
    // 3. Confirm
    await page.getByTestId('create-branch-confirm').click();
    // Auto-opens editor
    await page.waitForURL(/\/resume\/[0-9a-f-]+$/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/resume\/[0-9a-f-]+$/);
    // Branch name visible in editor
    await expect(page.getByRole('heading', { name: '后端-Go' })).toBeVisible();
  });
});

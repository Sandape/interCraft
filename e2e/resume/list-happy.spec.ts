// spec: spec/test.plan.md
// 3.1. resume list shows branches
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('resume', () => {
  test('resume list shows branches', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/resume');

    // ResumeList renders
    await expect(page.getByRole('heading', { name: '简历中心' })).toBeVisible();
    // Empty state (no branches yet)
    await expect(page.getByText('还没有简历')).toBeVisible();
  });
});

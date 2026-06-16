// spec: spec/test.plan.md
// 5.1. ability profile radar renders
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('ability-profile', () => {
  test('ability profile radar renders', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/ability-profile');

    await expect(page.getByRole('heading', { name: '能力画像' })).toBeVisible();
    // The live app uses these 6 dimensions (not the plan's labels)
    const dimensions = ['算法能力', '架构能力', '业务理解', '沟通表达', '工程实践', '技术深度'];
    for (const dim of dimensions) {
      await expect(page.getByText(dim).first()).toBeVisible();
    }
  });
});

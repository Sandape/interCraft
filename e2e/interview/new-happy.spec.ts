// spec: spec/test.plan.md
// 4.2. start new interview happy path
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('interview', () => {
  test('start new interview happy path', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/interview/new');

    // Setup form shows 目标岗位 + 目标公司
    await expect(page.getByRole('heading', { name: '开始模拟面试' })).toBeVisible();
    const target = page.getByRole('textbox', { name: '例如：高级前端工程师' });
    await target.fill('后端工程师');
    const company = page.getByRole('textbox', { name: '例如：字节跳动' });
    await company.fill('字节跳动');

    // Submit button enabled
    const submit = page.getByRole('button', { name: '开始面试' });
    await expect(submit).toBeEnabled();
    await submit.click();

    // Live interview page (streaming) - allow up to 30s for LLM stream
    await page.waitForURL(/\/interview\/[0-9a-f-]+\/live/, { timeout: 30_000 });
    await expect(page).toHaveURL(/\/interview\/[0-9a-f-]+\/live$/);
  });
});

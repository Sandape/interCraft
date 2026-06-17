// spec: specs/018-fix-product-defects/spec.md — User Story 2 (defect #12)
// Job 备注 must round-trip: the value typed in the create form must be
// visible in the list row after refresh. Backend already accepts notes_md;
// the bug is that the frontend was sending `note` instead.
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('job 备注 round-trip (notes_md)', () => {
  test('create with 备注 and see it in the row', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/jobs');
    await page.waitForURL(/\/jobs/, { timeout: 15_000 });

    await page.getByRole('button', { name: '添加职位' }).click();

    const marker = `NOTES_MD_${Date.now()}`;
    await page.getByPlaceholder('如：字节跳动').fill('Acme Co');
    await page.getByPlaceholder('如：高级前端工程师').fill('Senior Engineer');
    await page.getByPlaceholder('投递渠道、薪资范围等').fill(marker);

    await page.getByTestId('job-create-submit').click();

    // Row appears in the table with the marker visible — backend persisted
    // notes_md, frontend renders it.
    const row = page.locator('tbody tr', { hasText: 'Acme Co' });
    await expect(row).toBeVisible({ timeout: 10_000 });
    await expect(row).toContainText(marker);
  });
});

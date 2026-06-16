// spec: specs/018-fix-product-defects/spec.md — User Story 2 (defect #11)
// After 创建错题 the right-hand detail panel must render the new question
// immediately, without waiting for the React Query refetch round-trip.
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('error-book auto-select', () => {
  test('creating a question opens its detail immediately', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/error-book');
    await page.waitForURL(/\/error-book/, { timeout: 15_000 });

    await page.getByRole('button', { name: '添加错题' }).click();

    const marker = `AUTOSELECT_${Date.now()}`;
    await page.getByLabel('题目').fill(marker);
    await page.getByLabel('参考答案').fill('参考答案内容');

    await page.getByRole('button', { name: '保存' }).click();

    // The detail panel must appear with the newly created question text — no
    // manual refresh, no waiting for refetch. Generous timeout covers normal
    // POST round-trip, but it must beat any "still on empty state" flash.
    const detail = page.getByTestId('error-detail');
    await expect(detail).toBeVisible({ timeout: 3_000 });
    await expect(detail).toContainText(marker);
  });
});

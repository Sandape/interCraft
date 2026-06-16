// spec: spec/test.plan.md
// 4.7. negative: new interview with empty fields blocked
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('interview', () => {
  test('new interview submit disabled with empty fields', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/interview/new');
    const submit = page.getByRole('button', { name: '开始面试' });
    await expect(submit).toBeDisabled();
  });
});

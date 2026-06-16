// spec: specs/018-fix-product-defects/spec.md — User Story 2 (defect #6)
// Interview setup phase must let the user pick a resume branch and must
// submit branch_id when starting the interview.
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('interview setup — resume pick (branch_id)', () => {
  test('with no resumes, setup shows disabled picker + create link', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/interview/new');
    await page.waitForURL(/\/interview/, { timeout: 15_000 });

    // The new picker is a labelled region / select. With zero branches it
    // should be disabled and surface a CTA to /resume.
    const picker = page.getByTestId('setup-resume-picker');
    await expect(picker).toBeVisible();
    await expect(picker.locator('select')).toBeDisabled();
    await expect(picker).toContainText(/暂无可用简历|创建简历|新建简历/);
  });

  test('creating a resume makes the picker enabled', async ({ page }) => {
    await ensureFreshAccount(page);

    // Seed a resume branch directly through the backend API (UI modal
    // selectors vary across versions). Only the `name` field is required.
    const accessToken = await page.evaluate(() => sessionStorage.getItem('ic.access_token'));
    const resp = await page.request.post('http://localhost:8000/api/v1/resume-branches', {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: { name: 'E2E Branch', company: null, position: null, is_main: true },
    });
    expect(resp.status()).toBe(201);

    await page.goto('/interview/new');
    const picker = page.getByTestId('setup-resume-picker');
    await expect(picker).toBeVisible();
    await expect(picker.locator('select')).toBeEnabled();
  });
});

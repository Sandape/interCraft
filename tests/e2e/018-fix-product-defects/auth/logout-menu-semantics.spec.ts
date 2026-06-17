// spec: specs/018-fix-product-defects/spec.md — User Story 2 (defect #13)
// The Topbar user-menu 退出登录 button must be reachable by accessible
// name (not lost in a danger-color group) and trigger /login navigation.
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('logout menu semantics', () => {
  test.beforeEach(async ({ page }) => {
    // Pre-seed tokens BEFORE navigating so the AuthGuard's useCurrentUser
    // resolves to 'authenticated' and PublicOnly redirects /login away.
    await ensureFreshAccount(page);
    await page.goto('/dashboard');
    await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
  });

  test('退出登录 is a uniquely-named menuitem', async ({ page }) => {
    await page.getByTestId('topbar-user-menu-button').click();
    const logoutBtn = page.getByRole('menuitem', { name: '退出登录' });
    await expect(logoutBtn).toBeVisible();
    await expect(logoutBtn).toHaveCount(1);
  });

  test('退出登录 is not styled with danger / red color', async ({ page }) => {
    await page.getByTestId('topbar-user-menu-button').click();
    const logoutBtn = page.getByRole('menuitem', { name: '退出登录' });
    await expect(logoutBtn).toBeVisible();
    const classes = await logoutBtn.getAttribute('class');
    expect(classes ?? '').not.toContain('text-red');
  });

  test('clicking 退出登录 navigates to /login', async ({ page }) => {
    await page.getByTestId('topbar-user-menu-button').click();
    await page.getByRole('menuitem', { name: '退出登录' }).click();
    await page.waitForURL(/\/login/, { timeout: 10_000 });
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible();
  });
});

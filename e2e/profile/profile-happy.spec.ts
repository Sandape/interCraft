// spec: spec/test.plan.md
// 6.1. profile shows user info and avatar
// NOTE: live app uses /settings (个人资料 tab) for profile editing,
// not /profile. /profile renders the "个人能力画像" (ability profile) view.
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('profile', () => {
  test('settings page shows user info and avatar', async ({ page }) => {
    await ensureFreshAccount(page);
    await page.goto('/settings');

    await expect(page.getByRole('heading', { name: '设置' })).toBeVisible();
    // 基础信息 section
    await expect(page.getByText('基础信息')).toBeVisible();
    // 更换头像 button (initial-fallback avatar is rendered with user initials)
    await expect(page.getByRole('button', { name: '更换头像' })).toBeVisible();
    // Email is read-only
    await expect(page.getByText('邮箱不可修改')).toBeVisible();
  });
});

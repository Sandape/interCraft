// spec: specs/018-fix-product-defects/spec.md — User Story 2 (defect #1)
// /register deep-link must show the registration form directly, not the login form.
import { test, expect } from '@playwright/test';

test.describe('register deep link', () => {
  test('/register shows registration form without toggle click', async ({ page }) => {
    await page.goto('/register');
    // Form should be in register mode immediately — no need to click 立即注册.
    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: '请输入你的姓名' })).toBeVisible();
    // Submit button must say 创建账号, not 登录.
    await expect(page.getByTestId('auth-submit')).toHaveText('创建账号');
  });

  test('/login?mode=register still works as register shortcut', async ({ page }) => {
    await page.goto('/login?mode=register');
    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: '请输入你的姓名' })).toBeVisible();
  });

  test('/login without mode query shows login form', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible();
    await expect(page.getByTestId('auth-submit')).toHaveText('登录');
  });
});
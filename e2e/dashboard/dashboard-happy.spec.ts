// spec: spec/test.plan.md
// 2.1. dashboard renders widgets after login
import { test, expect } from '@playwright/test';
import { ensureFreshAccount } from '../helpers/auth';

test.describe('dashboard', () => {
  test('dashboard renders widgets after login', async ({ page }) => {
    const email = await ensureFreshAccount(page);

    // 1. Land on /dashboard
    await page.goto('/dashboard');
    // Dashboard greets the user by name
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    // Stats widgets
    await expect(page.getByText('活跃简历')).toBeVisible();
    await expect(page.getByText('已完成面试')).toBeVisible();
    await expect(page.getByText('综合能力')).toBeVisible();
    // Ability overview card
    await expect(page.getByText('能力概览')).toBeVisible();
    // Interview performance trend card
    await expect(page.getByText('面试表现趋势')).toBeVisible();
  });
});

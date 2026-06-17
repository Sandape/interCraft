// Shared auth helper. The plan's seed credential `tester@local` is rejected by
// the live backend's email validator (no TLD), so we dynamically register a
// fresh account per test session. Tokens live in sessionStorage under
// `ic.access_token` / `ic.refresh_token` (see src/api/token-storage.ts).
import { Page, expect } from '@playwright/test';

export const DEFAULT_PASSWORD = 'Passw0rd!';
export const API_BASE = process.env.E2E_API_BASE ?? 'http://127.0.0.1:8000';

export interface TestAccount {
  email: string;
  accessToken: string;
  refreshToken: string;
  userId: string;
}

export async function login(
  page: Page,
  email?: string,
  password: string = DEFAULT_PASSWORD,
): Promise<void> {
  if (!email) {
    email = (await ensureFreshAccount(page)).email;
  }

  await page.goto('/login');
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible();
  await page.getByTestId('email-input').fill(email);
  await page.getByTestId('password-input').fill(password);
  await page.getByTestId('auth-submit').click();
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
}

export async function ensureFreshAccount(page: Page): Promise<TestAccount> {
  const email = `e2e+${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
  const resp = await page.request.post(`${API_BASE}/api/v1/auth/register`, {
    data: { email, password: DEFAULT_PASSWORD, display_name: 'E2E Tester' },
  });
  if (!resp.ok()) {
    throw new Error(`Failed to create test account: ${resp.status()} ${await resp.text()}`);
  }
  const body = await resp.json();
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const target = `${API_BASE}${url.pathname}${url.search}`;
    const response = await route.fetch({ url: target });
    await route.fulfill({ response });
  });
  // Seed sessionStorage before the app boots on the next navigation. AuthGuard
  // reads tokens synchronously, then useCurrentUser resolves the store status.
  await page.addInitScript(
    ([access, refresh]) => {
      sessionStorage.setItem('ic.access_token', access);
      sessionStorage.setItem('ic.refresh_token', refresh);
    },
    [body.tokens.access_token, body.tokens.refresh_token],
  );
  return {
    email,
    accessToken: body.tokens.access_token,
    refreshToken: body.tokens.refresh_token,
    userId: body.user.id,
  };
}

export async function logout(page: Page): Promise<void> {
  await page.evaluate(() => {
    sessionStorage.removeItem('ic.access_token');
    sessionStorage.removeItem('ic.refresh_token');
  });
}

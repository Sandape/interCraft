/**
 * Round-2 — Auth Guard (4 tests).
 *
 * GUARD-01..04 verify D-016 (020 FIX-009): unauthenticated visitors to
 * protected routes are redirected to `/login`. Routes under test:
 *   - GUARD-01  /jobs
 *   - GUARD-02  /resume
 *   - GUARD-03  /error-book
 *   - GUARD-04  /interview
 *
 * Implementation: `src/App.tsx:43-95` wraps the protected `<Route>` subtree
 * in `<AuthGuard>`, which calls `requireAuth({ hasTokens, status })` from
 * `src/lib/requireAuth.ts`. When `hasTokens()` is false, the guard renders
 * `<Navigate to="/login" replace state={{ from: location }} />`.
 *
 * Each case uses a fresh browser context (no sessionStorage tokens) and
 * asserts the final URL is `/login`.
 */
import { test, expect } from '@playwright/test'

const PROTECTED_ROUTES = [
  { id: 'GUARD-01', path: '/jobs', label: '岗位' },
  { id: 'GUARD-02', path: '/resume', label: '简历' },
  { id: 'GUARD-03', path: '/error-book', label: '错题本' },
  { id: 'GUARD-04', path: '/interview', label: '面试' },
] as const

test.describe('F-R2. Auth Guard — Round-2', () => {
  for (const route of PROTECTED_ROUTES) {
    test(`${route.id} — unauthenticated visit to ${route.path} (${route.label}) redirects to /login`, async ({
      page,
      context,
    }) => {
      test.setTimeout(30_000)
      await context.clearCookies()
      // Use relative URL so Playwright routes through `baseURL` (localhost:5173).
      await page.goto(route.path, {
        waitUntil: 'domcontentloaded',
        timeout: 20_000,
      })
      await expect(page).toHaveURL(/\/login(\?.*)?$/, { timeout: 10_000 })
    })
  }

  test('GUARD-EXTRA — /login itself is reachable without a token', async ({ page, context }) => {
    test.setTimeout(20_000)
    await context.clearCookies()
    await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 20_000 })
    await expect(page).toHaveURL(/\/login(\?.*)?$/, { timeout: 10_000 })
  })

  test('GUARD-EXTRA-2 — /shared/:shareToken is reachable without a token (public route)', async ({
    page,
    context,
  }) => {
    test.setTimeout(20_000)
    await context.clearCookies()
    await page.goto('/shared/invalid-share-token', {
      waitUntil: 'domcontentloaded',
      timeout: 20_000,
    })
    await expect(page).not.toHaveURL(/\/login/, { timeout: 10_000 })
  })
})

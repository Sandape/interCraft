import { expect, test, type Page } from '@playwright/test'

const USER = {
  id: 'user-topbar-actions',
  email: 'topbar-actions@intercraft.test',
  display_name: 'Topbar Tester',
  title: 'Frontend Engineer',
  years_of_experience: 5,
  target_role: 'Senior Frontend Engineer',
  bio: null,
  subscription: 'pro',
  created_at: '2026-06-16T00:00:00Z',
  updated_at: '2026-06-16T00:00:00Z',
}

async function authenticate(page: Page) {
  await page.addInitScript(() => {
    sessionStorage.setItem('ic.access_token', 'e2e-access-token')
    sessionStorage.setItem('ic.refresh_token', 'e2e-refresh-token')
  })
}

async function routeCommon(page: Page) {
  await page.route('**/api/v1/users/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(USER) })
  })
}

async function openDashboard(page: Page) {
  await authenticate(page)
  await routeCommon(page)
  await page.goto('/dashboard')
  await expect(page.locator('[data-testid="topbar-user-menu-button"]')).toBeVisible()
}

test.describe('Topbar utility actions', () => {
  test.describe.configure({ mode: 'serial' })

  test('opens help and notification actions from the shell', async ({ page }) => {
    await openDashboard(page)

    await page.locator('[data-testid="topbar-help-button"]').click()
    await expect(page).toHaveURL(/\/help$/)

    await page.goto('/dashboard')
    await expect(page.locator('[data-testid="topbar-notifications-panel"]')).toHaveCount(0)

    const notifications = page.locator('[data-testid="topbar-notifications-button"]')
    await notifications.click()

    await expect(notifications).toHaveAttribute('aria-expanded', 'true')
    await expect(page.locator('[data-testid="topbar-notifications-panel"]')).toBeVisible()
    await expect(page.locator('[data-testid="topbar-notifications-settings"]')).toBeVisible()

    await page.keyboard.press('Escape')
    await expect(page.locator('[data-testid="topbar-notifications-panel"]')).toHaveCount(0)
    await expect(notifications).toHaveAttribute('aria-expanded', 'false')

    await notifications.click()
    await page.locator('[data-testid="topbar-notifications-settings"]').click()
    await expect(page).toHaveURL(/\/settings\?tab=notifications$/)
    await expect(page.locator('[data-testid="settings-panel-notifications"]')).toBeVisible()
  })

  test('routes avatar menu items to real destinations', async ({ page }) => {
    await openDashboard(page)

    await page.locator('[data-testid="topbar-user-menu-button"]').click()
    await expect(page.locator('[data-testid="topbar-user-menu"]')).toBeVisible()
    await page.locator('[data-testid="topbar-menu-profile"]').click()
    await expect(page).toHaveURL(/\/profile$/)

    await page.goto('/dashboard')
    await page.locator('[data-testid="topbar-user-menu-button"]').click()
    await page.locator('[data-testid="topbar-menu-settings"]').click()
    await expect(page).toHaveURL(/\/settings\?tab=profile$/)
    await expect(page.locator('[data-testid="settings-panel-profile"]')).toBeVisible()

    await page.goto('/dashboard')
    await page.locator('[data-testid="topbar-user-menu-button"]').click()
    await page.locator('[data-testid="topbar-menu-subscription"]').click()
    await expect(page).toHaveURL(/\/settings\?tab=subscription$/)
    await expect(page.locator('[data-testid="settings-panel-subscription"]')).toBeVisible()

    await page.goto('/dashboard')
    await page.locator('[data-testid="topbar-user-menu-button"]').click()
    await page.locator('[data-testid="topbar-menu-export"]').click()
    await expect(page).toHaveURL(/\/settings\?tab=export$/)
    await expect(page.locator('[data-testid="settings-panel-export"]')).toBeVisible()
  })

  test('supports reload-safe settings tab deep links', async ({ page }) => {
    await authenticate(page)
    await routeCommon(page)

    await page.goto('/settings?tab=export')
    await expect(page.locator('[data-testid="settings-panel-export"]')).toBeVisible()

    await page.locator('[data-testid="settings-nav-security"]').click()
    await expect(page).toHaveURL(/\/settings\?tab=security$/)
    await expect(page.locator('[data-testid="settings-panel-security"]')).toBeVisible()

    await page.reload()
    await expect(page.locator('[data-testid="settings-panel-security"]')).toBeVisible()

    await page.goto('/settings?tab=unknown')
    await expect(page.locator('[data-testid="settings-panel-profile"]')).toBeVisible()
  })

  test('keeps topbar popovers mutually exclusive', async ({ page }) => {
    await openDashboard(page)

    await page.locator('[data-testid="topbar-notifications-button"]').click()
    await expect(page.locator('[data-testid="topbar-notifications-panel"]')).toBeVisible()

    await page.locator('[data-testid="topbar-user-menu-button"]').click()
    await expect(page.locator('[data-testid="topbar-user-menu"]')).toBeVisible()
    await expect(page.locator('[data-testid="topbar-notifications-panel"]')).toHaveCount(0)
  })
})

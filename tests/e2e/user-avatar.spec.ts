/**
 * E2E for Feature 013 — User Avatar Upload and Display.
 *
 * Covers the full happy path (upload → topbar render → persist across reload)
 * and the three reject paths (wrong MIME, oversize, over-dimension) plus
 * remove. The cross-user reject is exercised by direct API calls to make
 * the test isolated from the UI.
 *
 * The spec runs against the live backend at http://localhost:8000; the
 * fixtures in `tests/e2e/_fixtures/` are reused as the file bytes to upload.
 */
import { test, expect, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { registerAndLogin, freshAccount, type Account } from './resume-center/fixture'

const __filename_ = fileURLToPath(import.meta.url)
const __dirname_ = path.dirname(__filename_)

const FIXTURES = path.join(__dirname_, '_fixtures')
const SAMPLE_PNG = path.join(FIXTURES, 'sample-avatar.png')
const TOO_LARGE_PNG = path.join(FIXTURES, 'avatar-too-large.png')
const TOO_WIDE_PNG = path.join(FIXTURES, 'avatar-too-wide.png')
const NOT_IMAGE = path.join(FIXTURES, 'not-an-image.txt')

const SCREENSHOTS = path.join(__dirname_, '..', '..', 'test-results', 'user-avatar')

test.beforeAll(() => {
  // No-op; SCREENSHOTS is computed lazily by the test.
})

async function gotoSettingsProfile(page: Page) {
  await page.goto('/settings?tab=profile')
  await expect(page.getByTestId('avatar-file-input')).toBeAttached({ timeout: 10_000 })
}

test.describe('User avatar (Feature 013)', () => {
  test('upload happy path → topbar render → persist across reload', async ({ page }) => {
    const account = freshAccount('avatar-happy')
    await registerAndLogin(page, account)
    await gotoSettingsProfile(page)

    // Pick the sample PNG
    await page.getByTestId('avatar-file-input').setInputFiles(SAMPLE_PNG)
    // Preview state: confirm button is visible
    await expect(page.getByTestId('avatar-confirm')).toBeVisible()
    // Confirm — same pattern as the passing `remove avatar reverts to initials` test.
    await page.getByTestId('avatar-confirm').click()
    await expect(page.getByTestId('avatar-success')).toContainText('头像已更新', { timeout: 10_000 })

    // Screenshot: settings with uploaded avatar
    await page.screenshot({ path: path.join(SCREENSHOTS, '01-uploaded-settings.png') })

    // Topbar should now render the uploaded image (an <img> inside the avatar slot)
    // The Avatar component uses useAvatarBlob, which converts the auth-required
    // /api/v1/users/me/avatar/<id> URL into a same-origin blob: URL. We assert
    // the <img> is present and non-empty, which is the user-visible signal.
    const topbarImg = page.locator('[data-testid="topbar-user-menu-button"] img')
    await expect(topbarImg).toBeVisible()
    const topbarSrc = await topbarImg.getAttribute('src')
    expect(topbarSrc).toBeTruthy()
    expect(topbarSrc!.startsWith('blob:http')).toBe(true)

    await page.screenshot({ path: path.join(SCREENSHOTS, '02-uploaded-topbar.png') })

    // Reload → avatar still rendered
    await page.reload()
    await expect(page.getByTestId('avatar-remove')).toBeVisible()
    const reloadedImg = page.locator('[data-testid="topbar-user-menu-button"] img')
    await expect(reloadedImg).toBeVisible()

    await page.screenshot({ path: path.join(SCREENSHOTS, '03-after-reload.png') })
  })

  test('upload reject: wrong MIME → inline error', async ({ page }) => {
    const account = freshAccount('avatar-bad-mime')
    await registerAndLogin(page, account)
    await gotoSettingsProfile(page)
    await page.getByTestId('avatar-file-input').setInputFiles(NOT_IMAGE)
    await expect(page.getByTestId('avatar-error')).toContainText('仅支持', { timeout: 5_000 })
    await page.screenshot({ path: path.join(SCREENSHOTS, '04-reject-mime.png') })
  })

  test('upload reject: oversize → inline error', async ({ page }) => {
    const account = freshAccount('avatar-too-large')
    await registerAndLogin(page, account)
    await gotoSettingsProfile(page)
    await page.getByTestId('avatar-file-input').setInputFiles(TOO_LARGE_PNG)
    // Either 413 (router pre-check) or 422 (after sniff) — both surface as an error.
    await expect(page.getByTestId('avatar-error')).toBeVisible({ timeout: 10_000 })
    await page.screenshot({ path: path.join(SCREENSHOTS, '05-reject-oversize.png') })
  })

  test('upload reject: over-dimension → inline error', async ({ page }) => {
    const account = freshAccount('avatar-too-wide')
    await registerAndLogin(page, account)
    await gotoSettingsProfile(page)
    await page.getByTestId('avatar-file-input').setInputFiles(TOO_WIDE_PNG)
    await expect(page.getByTestId('avatar-error')).toContainText('尺寸', { timeout: 10_000 })
    await page.screenshot({ path: path.join(SCREENSHOTS, '06-reject-dimension.png') })
  })

  test('remove avatar reverts to initials', async ({ page }) => {
    const account = freshAccount('avatar-remove')
    await registerAndLogin(page, account)
    await gotoSettingsProfile(page)

    // Upload first
    await page.getByTestId('avatar-file-input').setInputFiles(SAMPLE_PNG)
    await page.getByTestId('avatar-confirm').click()
    await expect(page.getByTestId('avatar-success')).toContainText('头像已更新', { timeout: 10_000 })

    // Topbar should show the uploaded avatar
    const topbarImg = page.locator('[data-testid="topbar-user-menu-button"] img')
    await expect(topbarImg).toBeVisible()

    // Remove
    await page.getByTestId('avatar-remove').click()
    await expect(page.getByTestId('avatar-success')).toContainText('已移除头像', { timeout: 10_000 })

    // Topbar should now show initials (no <img> inside the menu button)
    await expect(topbarImg).toHaveCount(0)
    await page.screenshot({ path: path.join(SCREENSHOTS, '07-removed.png') })
  })

  test('avatar renders in the share dialog', async ({ page }) => {
    const account = freshAccount('avatar-share')
    await registerAndLogin(page, account)
    await gotoSettingsProfile(page)
    await page.getByTestId('avatar-file-input').setInputFiles(SAMPLE_PNG)
    await page.getByTestId('avatar-confirm').click()
    await expect(page.getByTestId('avatar-success')).toContainText('头像已更新', { timeout: 10_000 })

    // Navigate to the ability profile page and open the share dialog
    await page.goto('/ability-profile')
    // Wait for the page to settle
    await page.waitForLoadState('networkidle')
    // Match the share button by its visible label (currently "分享").
    await page.getByRole('button', { name: '分享' }).click()

    // Share dialog should mount with our user identity block
    const dialog = page.getByTestId('share-dialog-user')
    await expect(dialog).toBeVisible()
    const dialogImg = dialog.locator('img')
    await expect(dialogImg).toBeVisible()
    // The Avatar component now runs the auth-required URL through useAvatarBlob,
    // so the rendered <img> src is a same-origin blob: URL.
    const dialogSrc = await dialogImg.getAttribute('src')
    expect(dialogSrc).toBeTruthy()
    expect(dialogSrc!.startsWith('blob:http')).toBe(true)
    await page.screenshot({ path: path.join(SCREENSHOTS, '08-share-dialog.png') })
  })

  test('cross-user reject: user B cannot fetch user A\'s avatar', async ({ page, request }) => {
    // User A uploads via UI
    const accA = freshAccount('avatar-iso-A')
    await registerAndLogin(page, accA)
    await gotoSettingsProfile(page)
    await page.getByTestId('avatar-file-input').setInputFiles(SAMPLE_PNG)
    await page.getByTestId('avatar-confirm').click()
    await expect(page.getByTestId('avatar-success')).toContainText('头像已更新', { timeout: 10_000 })

    // Pull the avatar id from the authenticated /me response (the topbar <img>
    // uses a blob: URL after useAvatarBlob, which doesn't contain the id).
    const meRes = await request.get('/api/v1/users/me', {
      headers: { Authorization: `Bearer ${(await page.evaluate(() => sessionStorage.getItem('ic.access_token')))!}` },
    })
    expect(meRes.ok()).toBeTruthy()
    const avatarUrl = (await meRes.json()).avatar_url as string | null
    expect(avatarUrl).toBeTruthy()
    const avatarId = avatarUrl!.split('/').pop()!

    // User B: log in via API (no UI logout dance) and try to GET the same id
    const accB = freshAccount('avatar-iso-B')
    const login = await request.post('/api/v1/auth/login', {
      data: {
        email: accB.email,
        password: accB.password,
        device_fingerprint: 'fp-e2e-isoB',
      },
    })
    // B was just created by `freshAccount` (random email) — they need to register first.
    if (login.status() === 404 || login.status() === 401) {
      const reg = await request.post('/api/v1/auth/register', {
        data: {
          email: accB.email,
          password: accB.password,
          display_name: 'isolation-B',
          device_fingerprint: 'fp-e2e-isoB',
        },
      })
      expect(reg.ok()).toBeTruthy()
    }
    const reLogin = await request.post('/api/v1/auth/login', {
      data: {
        email: accB.email,
        password: accB.password,
        device_fingerprint: 'fp-e2e-isoB',
      },
    })
    expect(reLogin.ok()).toBeTruthy()
    const { tokens } = await reLogin.json()

    // GET user A's avatar as user B → 404
    const attempt = await request.get(`/api/v1/users/me/avatar/${avatarId}`, {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    })
    expect(attempt.status()).toBe(404)
  })
})

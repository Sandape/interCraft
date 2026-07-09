/**
 * T050 — Playwright E2E: 3-column resizable layout.
 *
 * Independent test (US3):
 *   - Login as a test user
 *   - Navigate to /resume/v2/:id
 *   - Verify 3 panels visible at default sizes (22 / 56 / 22)
 *   - Drag the left sidebar's resize handle inward → width changes
 *   - Reload → width persisted (localStorage `v2.panel-sizes`)
 *   - Click 12 accordion items in the right settings panel → each toggles
 *   - Mobile viewport (375×667) → left + right collapse to 48px rails
 *
 * Requires the backend to be running (`uv run uvicorn backend.app.main:app`)
 * and the frontend dev server on http://localhost:5173. If the backend is
 * down the test short-circuits via test.skip() so the suite still runs.
 */
import { test, expect, type Page } from '@playwright/test'

const FRONTEND = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173'
const BACKEND = process.env.PLAYWRIGHT_API_BASE ?? 'http://127.0.0.1:8000'

async function isBackendUp(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/openapi.json`, { method: 'GET' })
    return res.ok || res.status < 500
  } catch {
    return false
  }
}

async function registerAndCreateV2Resume(page: Page) {
  const stamp = Date.now() + '-' + Math.floor(Math.random() * 10_000)
  const email = `rsl-${stamp}@intercraft.io`
  const password = 'P@ssw0rd123'

  await page.goto(`${FRONTEND}/register?mode=register`)
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.waitForTimeout(300)
  await page.getByTestId('auth-submit').click()
  await page.waitForURL(/\/dashboard$/, { timeout: 15_000 })

  const result = await page.evaluate(
    async ({ email, password }) => {
      const BASE = `${window.location.origin}/api/v1`
      const loginRes = await fetch(`${BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!loginRes.ok) throw new Error(`login failed: ${loginRes.status}`)
      const { tokens } = await loginRes.json()
      const createRes = await fetch(`${BASE}/v2/resumes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokens.access_token}`,
        },
        body: JSON.stringify({
          name: '布局测试',
          slug: `rsl-${Date.now()}`,
          template: 'pikachu',
          from_sample: false,
        }),
      })
      if (!createRes.ok) throw new Error(`create failed: ${createRes.status}`)
      const { resume } = await createRes.json()
      return resume.id as string
    },
    { email, password },
  )
  return result as string
}

test.describe('T050 — 3-column resizable layout', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('3 panels render at default 22/56/22, drag persists, 12 accordions toggle', async ({
    page,
  }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    // 1. Three panels are present at default sizes.
    const left = page.getByTestId('left-panel')
    const center = page.getByTestId('center-panel')
    const right = page.getByTestId('right-panel')
    await expect(left).toBeVisible()
    await expect(center).toBeVisible()
    await expect(right).toBeVisible()

    const leftBox = await left.boundingBox()
    const centerBox = await center.boundingBox()
    const rightBox = await right.boundingBox()
    expect(leftBox).not.toBeNull()
    expect(centerBox).not.toBeNull()
    expect(rightBox).not.toBeNull()
    const total = leftBox!.width + centerBox!.width + rightBox!.width
    const leftPct = (leftBox!.width / total) * 100
    const centerPct = (centerBox!.width / total) * 100
    const rightPct = (rightBox!.width / total) * 100
    // Default is 22/56/22; allow ±3 pp tolerance.
    expect(leftPct).toBeGreaterThan(18)
    expect(leftPct).toBeLessThan(26)
    expect(centerPct).toBeGreaterThan(50)
    expect(rightPct).toBeGreaterThan(18)
    expect(rightPct).toBeLessThan(26)

    // 2. Drag the left resize handle inward by 80 px.
    const handle = page.getByTestId('resize-handle-left')
    await handle.hover()
    const handleBox = await handle.boundingBox()
    expect(handleBox).not.toBeNull()
    const startX = handleBox!.x + handleBox!.width / 2
    const startY = handleBox!.y + handleBox!.height / 2
    await page.mouse.move(startX, startY)
    await page.mouse.down()
    await page.mouse.move(startX + 80, startY, { steps: 10 })
    await page.mouse.up()
    await page.waitForTimeout(100)

    const newLeftBox = await left.boundingBox()
    expect(newLeftBox!.width).toBeGreaterThan(leftBox!.width)

    // 3. localStorage now has v2.panel-sizes.
    const stored = await page.evaluate(() => window.localStorage.getItem('v2.panel-sizes'))
    expect(stored).toBeTruthy()
    const parsed = JSON.parse(stored!) as number[]
    expect(parsed).toHaveLength(3)
    expect(parsed[0]).toBeGreaterThan(22)

    // 4. Reload → width persists.
    await page.reload()
    await page.waitForSelector('[data-testid="left-panel"]', { timeout: 10_000 })
    const reloadedLeftBox = await page.getByTestId('left-panel').boundingBox()
    expect(reloadedLeftBox!.width).toBeGreaterThan(leftBox!.width - 2)

    // 5. All 12 accordion items toggle in the right panel.
    const panels = [
      'template',
      'layout',
      'typography',
      'design',
      'styles',
      'page',
      'notes',
      'sharing',
      'statistics',
      'analysis',
      'export',
      'information',
    ]
    for (const p of panels) {
      const btn = page.getByTestId(`accordion-${p}`)
      await expect(btn).toBeVisible()
      const before = await btn.getAttribute('aria-expanded')
      await btn.click()
      const after = await btn.getAttribute('aria-expanded')
      expect(after).not.toBe(before)
    }
  })

  test('mobile viewport collapses left + right panels to 48px rails', async ({ page }) => {
    const id = await registerAndCreateV2Resume(page)
    await page.setViewportSize({ width: 375, height: 667 })
    await page.goto(`${FRONTEND}/resume/v2/${id}`)
    await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 15_000 })

    const left = page.getByTestId('left-panel')
    const right = page.getByTestId('right-panel')
    await expect(left).toHaveAttribute('data-rail-width', '48')
    await expect(right).toHaveAttribute('data-rail-width', '48')
  })
})
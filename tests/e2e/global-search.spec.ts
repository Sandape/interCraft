import { expect, test, type Page } from '@playwright/test'

const USER = {
  id: 'user-global-search',
  email: 'global-search@intercraft.test',
  display_name: 'Search Tester',
  title: 'Frontend Engineer',
  years_of_experience: 5,
  target_role: 'Senior Frontend Engineer',
  bio: null,
  subscription: 'pro',
  created_at: '2026-06-16T00:00:00Z',
  updated_at: '2026-06-16T00:00:00Z',
}

const RESUMES = [
  {
    id: 'branch-bytedance',
    parent_id: null,
    name: '字节跳动 · 高级前端',
    company: '字节跳动',
    position: '高级前端工程师',
    status: 'optimizing',
    match_score: 92,
    is_main: false,
    is_pinned: false,
    style_preference: 'modern',
    last_edited_at: '2026-06-15T00:00:00Z',
    created_at: '2026-06-10T00:00:00Z',
    updated_at: '2026-06-15T00:00:00Z',
    version_count: 3,
    block_count: 8,
  },
  {
    id: 'branch-tencent',
    parent_id: null,
    name: '腾讯 · 后端架构',
    company: '腾讯',
    position: '后端工程师',
    status: 'ready',
    match_score: 85,
    is_main: true,
    is_pinned: false,
    style_preference: 'classic',
    last_edited_at: '2026-06-12T00:00:00Z',
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-12T00:00:00Z',
    version_count: 5,
    block_count: 12,
  },
]

const SESSIONS = [
  {
    id: 'session-bytedance-1',
    mode: 'text',
    status: 'completed',
    position: '高级前端工程师',
    company: '字节跳动',
    score: 86,
    overall_score: 86,
    duration_seconds: 480,
    question_count: 5,
    thread_id: 'thread-1',
    created_at: '2026-06-15T00:00:00Z',
    updated_at: '2026-06-15T00:08:00Z',
  },
]

const SEARCH_RESULTS_BYTEDANCE = {
  groups: [
    {
      type: 'resume',
      label: '简历分支',
      items: [
        {
          id: 'branch-bytedance',
          type: 'resume',
          title: '字节跳动 · 高级前端',
          subtitle: '高级前端工程师',
          destination: '/resume/branch-bytedance',
          score: 1.0,
          meta: { branch_status: 'optimizing', is_main: false },
        },
      ],
      total: 1,
    },
    {
      type: 'interview',
      label: '面试记录',
      items: [
        {
          id: 'session-bytedance-1',
          type: 'interview',
          title: '字节跳动 · 高级前端',
          subtitle: '字节跳动',
          destination: '/interview/session-bytedance-1/report',
          score: 1.0,
          meta: { session_status: 'completed' },
        },
      ],
      total: 1,
    },
  ],
  query: '字节',
  took_ms: 12,
}

const SEARCH_RESULTS_EMPTY = {
  groups: [],
  query: 'zzzznotfound',
  took_ms: 4,
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
  await page.route('**/api/v1/resume-branches**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: RESUMES, total: RESUMES.length, limit: 50, offset: 0 }),
    })
  })
  await page.route('**/api/v1/interview-sessions**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: SESSIONS, total: SESSIONS.length, limit: 50, offset: 0 }),
      })
    } else {
      await route.continue()
    }
  })
}

async function openDashboard(page: Page) {
  await authenticate(page)
  await routeCommon(page)
  await page.goto('/dashboard')
  await expect(page.locator('[data-testid="topbar-user-menu-button"]')).toBeVisible()
  await expect(page.locator('[data-testid="topbar-search-input"]')).toBeVisible()
  // Wait for the global keydown listener (registered in AppShell's useEffect) to be wired up.
  await page.waitForTimeout(50)
}

test.describe('Global search command palette', () => {
  test.describe.configure({ mode: 'serial' })

  test('US1: opens via shortcut, types, and clicks a result to navigate', async ({ page }) => {
    let searchRequest: URL | null = null
    await page.route('**/api/v1/search**', async (route) => {
      searchRequest = new URL(route.request().url())
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SEARCH_RESULTS_BYTEDANCE),
      })
    })

    await openDashboard(page)

    // The topbar search input is visible and opens the palette on click
    const searchInput = page.locator('[data-testid="topbar-search-input"]')
    await expect(searchInput).toBeVisible()
    await searchInput.click()

    const palette = page.locator('[data-testid="command-palette"]')
    await expect(palette).toBeVisible()
    await expect(page.locator('[data-testid="command-palette-input"]')).toBeFocused()

    // Type a query
    await page.locator('[data-testid="command-palette-input"]').fill('字节')
    await expect(page.locator('[data-testid="command-palette-group-resume"]')).toBeVisible()
    await expect(page.locator('[data-testid="command-palette-group-interview"]')).toBeVisible()
    await expect(page.locator('[data-testid="command-palette-result-branch-bytedance"]')).toBeVisible()

    // Verify the request was made with the truncated query
    expect(searchRequest).not.toBeNull()
    expect(searchRequest!.searchParams.get('q')).toBe('字节')

    // Click the first result and verify navigation
    await page.locator('[data-testid="command-palette-result-branch-bytedance"]').click()
    await expect(page).toHaveURL(/\/resume\/branch-bytedance$/)
    await expect(palette).toHaveCount(0)
  })

  test('US2: keyboard navigation moves highlight and Enter navigates', async ({ page }) => {
    await page.route('**/api/v1/search**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SEARCH_RESULTS_BYTEDANCE),
      })
    })

    await openDashboard(page)
    await page.keyboard.press('Control+k')
    await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()

    await page.locator('[data-testid="command-palette-input"]').fill('字节')
    await expect(page.locator('[data-testid="command-palette-group-resume"]')).toBeVisible()

    // First result is highlighted by default
    const first = page.locator('[data-testid="command-palette-result-branch-bytedance"]')
    const second = page.locator('[data-testid="command-palette-result-session-bytedance-1"]')
    await expect(first).toHaveAttribute('aria-selected', 'true')

    // ArrowDown moves to the second result
    await page.keyboard.press('ArrowDown')
    await expect(second).toHaveAttribute('aria-selected', 'true')

    // ArrowUp returns to the first
    await page.keyboard.press('ArrowUp')
    await expect(first).toHaveAttribute('aria-selected', 'true')

    // Enter on the first result navigates
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/resume\/branch-bytedance$/)

    // Escape closes the palette without navigating
    await page.goto('/dashboard')
    await expect(page.locator('[data-testid="topbar-user-menu-button"]')).toBeVisible()
    await expect(page.locator('[data-testid="topbar-search-input"]')).toBeVisible()
    await page.keyboard.press('Control+k')
    await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('[data-testid="command-palette"]')).toHaveCount(0)
    await expect(page).toHaveURL(/\/dashboard$/)
  })

  test('US3: shows empty hint and no-results message', async ({ page }) => {
    let lastQuery = ''
    await page.route('**/api/v1/search**', async (route) => {
      lastQuery = new URL(route.request().url()).searchParams.get('q') ?? ''
      if (lastQuery === 'slowsearch') {
        await new Promise((resolve) => setTimeout(resolve, 350))
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SEARCH_RESULTS_EMPTY),
      })
    })

    await openDashboard(page)
    await page.keyboard.press('Control+k')
    await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()
    await expect(page.locator('[data-testid="command-palette-empty-hint"]')).toBeVisible()

    // No request should be sent while the input is empty
    expect(lastQuery).toBe('')

    // Type a non-matching query and verify no-results state
    await page.locator('[data-testid="command-palette-input"]').fill('slowsearch')
    await expect(page.locator('[data-testid="command-palette-loading"]')).toBeVisible()
    await expect(page.locator('[data-testid="command-palette-no-results"]')).toBeVisible()
    expect(lastQuery).toBe('slowsearch')

    await page.locator('[data-testid="command-palette-input"]').fill('zzzznotfound')
    await expect.poll(() => lastQuery).toBe('zzzznotfound')
    await expect(page.locator('[data-testid="command-palette-no-results"]')).toBeVisible()
  })

  test('US4: shortcut suppressed on /login; outside click closes; error state is retryable', async ({ page }) => {
    let errorMode = false
    let lastQuery = ''
    await page.route('**/api/v1/search**', async (route) => {
      lastQuery = new URL(route.request().url()).searchParams.get('q') ?? ''
      if (errorMode) {
        await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'boom' }) })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(SEARCH_RESULTS_BYTEDANCE),
        })
      }
    })

    // Public page: shortcut must NOT open the palette
    await page.goto('/login')
    await page.keyboard.press('Control+k')
    await expect(page.locator('[data-testid="command-palette"]')).toHaveCount(0)

    // Authenticated: shortcut opens
    await openDashboard(page)
    await page.keyboard.press('Control+k')
    await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()

    // Press the shortcut again to toggle closed
    await page.keyboard.press('Control+k')
    await expect(page.locator('[data-testid="command-palette"]')).toHaveCount(0)

    // Outside click closes
    await page.keyboard.press('Control+k')
    await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()
    await page.locator('[data-testid="command-palette-overlay"]').click({ position: { x: 10, y: 10 } })
    await expect(page.locator('[data-testid="command-palette"]')).toHaveCount(0)

    // Error state: palette stays open and retry works
    errorMode = true
    await page.keyboard.press('Control+k')
    await page.locator('[data-testid="command-palette-input"]').fill('字节')
    await expect(page.locator('[data-testid="command-palette-error"]')).toBeVisible()
    // Palette remains open during error
    await expect(page.locator('[data-testid="command-palette"]')).toBeVisible()

    // Retry returns the success state
    errorMode = false
    await page.locator('[data-testid="command-palette-retry"]').click()
    await expect(page.locator('[data-testid="command-palette-group-resume"]')).toBeVisible()
    expect(lastQuery).toBe('字节')
  })
})

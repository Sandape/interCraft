import { expect, test } from '@playwright/test'

const USER = {
  id: 'user-resume-guardrails',
  email: 'resume-guardrails@intercraft.test',
  display_name: 'Resume Guardrails Tester',
  title: 'Frontend Engineer',
  years_of_experience: 5,
  target_role: 'Senior Frontend Engineer',
  bio: null,
  subscription: 'pro',
  created_at: '2026-06-16T00:00:00Z',
  updated_at: '2026-06-16T00:00:00Z',
}

const IN_PROGRESS_SESSION = {
  id: 'session-in-progress',
  branch_id: null,
  position: 'Senior Frontend Engineer',
  company: 'InterCraft',
  mode: 'text',
  status: 'in_progress',
  thread_id: 'thread-in-progress',
  started_at: '2026-06-16T00:00:00Z',
  ended_at: null,
  duration_sec: 185,
  overall_score: null,
  created_at: '2026-06-16T00:00:00Z',
  updated_at: '2026-06-16T00:03:05Z',
}

const COMPLETED_SESSION = {
  ...IN_PROGRESS_SESSION,
  id: 'session-completed',
  status: 'completed',
  ended_at: '2026-06-16T00:08:00Z',
  duration_sec: 480,
  overall_score: 86,
}

const RESUME_VALUES = {
  values: {
    messages: [
      { role: 'user', content: 'I have five years of frontend experience and focus on platform UI.' },
      { role: 'assistant', content: 'Describe a complex state management decision you made.' },
      { type: 'human', content: 'I split server cache and local UI state, then added tests around invalidation.' },
    ],
    questions: [
      {
        question: 'Describe a complex state management decision you made.',
        dimension: 'System Design',
        expected_points: ['tradeoffs', 'data ownership'],
        hints: ['Mention cache boundaries'],
      },
    ],
    scores: [
      {
        question_no: 1,
        score: 8,
        dimension: 'System Design',
        feedback: 'Clear tradeoffs and concrete implementation detail.',
        sub_scores: { clarity: 8, depth: 8 },
      },
    ],
  },
}

async function authenticate(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    sessionStorage.setItem('ic.access_token', 'e2e-access-token')
    sessionStorage.setItem('ic.refresh_token', 'e2e-refresh-token')
  })
}

async function routeCommon(page: import('@playwright/test').Page) {
  await page.route('**/api/v1/users/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(USER) })
  })

  await page.route('**/api/v1/error-questions**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [] }) })
  })

  await page.route('**/api/v1/resume-branches**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
  })

  await page.route(/\/api\/v1\/interview-sessions(?:\?.*)?$/, async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: [IN_PROGRESS_SESSION, COMPLETED_SESSION] }),
      })
      return
    }

    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ data: { ...IN_PROGRESS_SESSION, id: 'session-created', status: 'pending' } }),
    })
  })

  await page.route(/\/api\/v1\/interview-sessions\/session-completed$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(COMPLETED_SESSION) })
  })

  await page.route(/\/api\/v1\/interview-sessions\/session-in-progress$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(IN_PROGRESS_SESSION) })
  })

  await page.route(/\/api\/v1\/interview-sessions\/session-in-progress\/resume$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: RESUME_VALUES }) })
  })
}

test.describe('Interview Resume Guardrails', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page)
    await routeCommon(page)
  })

  test('resumes an in-progress interview from the list', async ({ page }) => {
    await page.goto('/interview')

    const card = page.locator('[data-testid="session-card"][data-session-id="session-in-progress"]')
    await expect(card).toBeVisible()

    await page.locator('[data-testid="continue-interview-session-in-progress"]').click()

    await expect(page).toHaveURL(/\/interview\/session-in-progress\/live/)
    await expect(page.locator('[data-testid="resumed-notice"]')).toBeVisible()
    await expect(page.locator('[data-testid="resume-summary"]')).toContainText('2')
    await expect(page.locator('[data-testid="restored-answer-0"]')).toContainText('five years')
    await expect(page.locator('[data-testid="restored-answer-1"]')).toContainText('server cache')
    await expect(page.locator('[data-testid="answer-input"]')).toBeVisible()
    await page.screenshot({ path: 'test-results/interview-resume-guardrails/resume-success.png', fullPage: true })
  })

  test('shows a retryable resume error instead of the setup form', async ({ page }) => {
    await page.route(/\/api\/v1\/interview-sessions\/session-in-progress\/resume$/, async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'resume.failed', message: 'Resume unavailable' } }),
      })
    })

    await page.goto('/interview/session-in-progress/live')

    await expect(page.locator('[data-testid="resume-error-state"]')).toBeVisible()
    await expect(page.locator('[data-testid="resume-error-message"]')).toBeVisible()
    await expect(page.locator('[data-testid="resume-retry"]')).toBeVisible()
    await expect(page.locator('[data-testid="resume-return-list"]')).toBeVisible()
    await expect(page.locator('input[name="position"]')).toHaveCount(0)
    await page.screenshot({ path: 'test-results/interview-resume-guardrails/resume-error.png', fullPage: true })
  })

  test('opens a completed session without creating a duplicate session', async ({ page }) => {
    const createRequests: string[] = []
    page.on('request', (request) => {
      if (request.method() === 'POST' && request.url().endsWith('/api/v1/interview-sessions')) {
        createRequests.push(request.url())
      }
    })

    await page.goto('/interview/session-completed/live')

    await expect(page.locator('[data-testid="interview-completed-state"]')).toBeVisible()
    expect(createRequests).toHaveLength(0)
    await page.screenshot({ path: 'test-results/interview-resume-guardrails/completed-state.png', fullPage: true })
  })
})

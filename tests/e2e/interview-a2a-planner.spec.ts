/**
 * 025 — A2A Interview Planner E2E (T031 + T032, REQ-12).
 *
 * Tests the A2A planner integration end-to-end:
 *
 *   HAPPY-02  Full flow: create session → start → submit answer (planner runs)
 *             → interview_plan populated → frontend plan toggle visible
 *             → report includes interview_plan.
 *
 *   BC-01    Backward compatibility: an old interview record (without plan)
 *            returns null interview_plan in both GET session and GET report
 *            without crashing.
 *
 * Pre-conditions:
 *   - Backend started with LLM_MOCK_MODE=1, TAVILY_MOCK_MODE=1, and
 *     TAVILY_MOCK_SCENARIO_PATH=<abs path to active.json>
 *   - Frontend dev server running (http://localhost:5173) for UI tests
 *
 * Implementation references:
 *   - backend/app/agents/interview/state.py (InterviewGraphState includes
 *     interview_plan / web_research)
 *   - backend/app/agents/interview/schemas.py (InterviewPlan model)
 *   - backend/app/agents/tools/tavily_search.py + tavily_client_mock.py
 *   - backend/app/modules/interviews/service.py (persist + get_report)
 *   - src/pages/InterviewLive.tsx ([data-testid="interview-plan-toggle"])
 *   - src/pages/InterviewReport.tsx (plan display section)
 */
import { test, expect, type APIRequestContext } from '@playwright/test'
import { registerUser, API_BASE, FRONTEND_BASE } from './round-1/fixtures/auth'
import { authHeader, createBranch } from './round-1/helpers/api'
import { dbQuery } from './round-1/helpers/db'
import { writeTavilyScenarioFile, HAPPY_PLANNER_SCENARIO, EMPTY_SEARCH_SCENARIO } from './round-2/fixtures/tavily-mock'
import { randomUUID } from 'node:crypto'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function createSession(
  request: APIRequestContext,
  token: string,
  branchId: string,
  position = '前端开发',
  company = '字节跳动',
): Promise<string> {
  const res = await request.post(`${API_BASE}/api/v1/interview-sessions`, {
    headers: authHeader(token),
    data: { branch_id: branchId, position, company },
  })
  expect([200, 201, 202]).toContain(res.status())
  const body = await res.json()
  const sessionId = body.data?.id ?? body.id
  expect(sessionId).toBeTruthy()
  return sessionId as string
}

async function startSession(request: APIRequestContext, token: string, sessionId: string): Promise<void> {
  const res = await request.post(`${API_BASE}/api/v1/interview-sessions/${sessionId}/start`, {
    headers: authHeader(token),
  })
  expect(res.status()).toBeGreaterThanOrEqual(200)
  expect(res.status()).toBeLessThan(300)
}

async function submitAnswer(
  request: APIRequestContext,
  token: string,
  sessionId: string,
  answer: string,
  sequenceNo = 0,
): Promise<{ status: number; body: Record<string, unknown> }> {
  const res = await request.post(`${API_BASE}/api/v1/interview-sessions/${sessionId}/answers`, {
    headers: authHeader(token),
    data: { content: answer, sequence_no: sequenceNo },
  })
  const body: Record<string, unknown> = await res.json()
  return { status: res.status(), body }
}

async function getSession(
  request: APIRequestContext,
  token: string,
  sessionId: string,
): Promise<Record<string, unknown>> {
  const res = await request.get(`${API_BASE}/api/v1/interview-sessions/${sessionId}`, {
    headers: authHeader(token),
  })
  expect(res.status()).toBe(200)
  return (await res.json()) as Record<string, unknown>
}

function createCompletedReport(userId: string, sessionId: string): void {
  const reportId = randomUUID()
  dbQuery(
    `INSERT INTO interview_reports
     (id, session_id, overall_score, per_question_score, dimension_scores,
      strengths, improvements, summary_md, generated_at, created_at, updated_at)
     VALUES (
       '${reportId}', '${sessionId}', 7.5, '[]'::jsonb, '[]'::jsonb,
       '[]'::jsonb, '[]'::jsonb, 'Mock report for E2E', NOW(), NOW(), NOW()
     )`,
    { userId },
  )
  dbQuery(
    `UPDATE interview_sessions
     SET status = 'completed', ended_at = NOW(), duration_sec = 600, overall_score = 7.5
     WHERE id = '${sessionId}'`,
    { userId },
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('025 — A2A Interview Planner E2E', () => {
  test('HAPPY-02 — Full flow: planner runs, plan visible on page and in report', async ({
    request,
    page,
    context,
  }) => {
    test.setTimeout(120_000)

    // Write Tavily happy scenario before the test
    writeTavilyScenarioFile(HAPPY_PLANNER_SCENARIO)

    // 1) Register user + create branch
    const user = await registerUser(request, 'e2e-025-happy')
    const branch = await createBranch(request, user.access_token, {
      name: '025-HAPPY-branch',
      company: '字节跳动',
      position: '前端开发',
    })

    // 2) Create + start session
    const sessionId = await createSession(request, user.access_token, branch.id, '前端开发', '字节跳动')
    await startSession(request, user.access_token, sessionId)

    // 3) Submit first answer — this triggers the planner subgraph via the
    //    supervisor graph. The planner populates interview_plan in the graph
    //    state and the service persists it to DB. We assert directly on the
    //    graph-produced plan (no DB injection fallback) so the test fails
    //    loudly if A2A routing breaks.
    const { status, body } = await submitAnswer(request, user.access_token, sessionId, '我的自我介绍...', 0)
    expect(status).toBe(200)

    // The graph result must include at least one generated question — that
    // proves the planner ran, planner_complete forwarded state, and the
    // interviewer (question_gen) node executed.
    const result = (body.data ?? body) as Record<string, unknown>
    const questions = (result.questions as unknown[]) ?? []
    expect(questions.length).toBeGreaterThanOrEqual(1)

    // 4) The plan must be persisted by the graph (not injected by the test).
    const sess = await getSession(request, user.access_token, sessionId)
    expect(sess.interview_plan).toBeTruthy()
    const plan = sess.interview_plan as Record<string, unknown>
    // target_company / target_position must reflect the session, not LLM
    // imagination. The planner_validate node uses `or` fallback to the
    // session context, so these should always be the values we passed in.
    expect(plan.target_company).toBe('字节跳动')
    expect(plan.target_position).toBe('前端开发')

    // 5) Frontend: navigate to InterviewLive page and verify plan toggle is visible.
    await context.addInitScript((token: string) => {
      sessionStorage.setItem('ic.access_token', token)
      sessionStorage.setItem('ic.refresh_token', token)
    }, user.access_token)

    await page.goto(`${FRONTEND_BASE}/interview/${sessionId}/live`, {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    })
    const planToggle = page.locator('[data-testid="interview-plan-toggle"]')
    await expect(planToggle).toBeVisible({ timeout: 30_000 })
    await expect(planToggle).toContainText('面试计划')

    // 6) Create a report in DB and verify GET /report includes interview_plan
    createCompletedReport(user.user_id, sessionId)

    const reportRes = await request.get(
      `${API_BASE}/api/v1/interview-sessions/${sessionId}/report`,
      { headers: authHeader(user.access_token) },
    )
    expect(reportRes.status()).toBe(200)
    const reportBody = await reportRes.json()
    const reportData = reportBody.data ?? reportBody
    expect(reportData.interview_plan).toBeTruthy()
    // Plan fields should be present
    const reportPlan = reportData.interview_plan as Record<string, unknown>
    expect(reportPlan.target_company || reportPlan.target_position).toBeTruthy()
  })

  test('BC-01 — Backward compatibility: old session without plan displays correctly', async ({
    request,
    page,
    context,
  }) => {
    test.setTimeout(60_000)

    writeTavilyScenarioFile(EMPTY_SEARCH_SCENARIO)

    const user = await registerUser(request, 'e2e-025-bc')
    const branch = await createBranch(request, user.access_token, {
      name: '025-BC-branch',
      company: 'TestCo',
      position: 'SWE',
    })

    // Create a session but do NOT submit any answer — the planner never runs,
    // so interview_plan remains NULL in the DB.
    const sessionId = await createSession(request, user.access_token, branch.id, 'SWE', 'TestCo')

    // 1) GET session returns interview_plan = null
    const sess = await getSession(request, user.access_token, sessionId)
    expect(sess.interview_plan).toBeNull()

    // 2) Create a report + set session to completed (simulating old completed session)
    createCompletedReport(user.user_id, sessionId)

    // 3) GET /report returns interview_plan = null (no crash)
    const reportRes = await request.get(
      `${API_BASE}/api/v1/interview-sessions/${sessionId}/report`,
      { headers: authHeader(user.access_token) },
    )
    expect(reportRes.status()).toBe(200)
    const reportBody = await reportRes.json()
    const reportData = reportBody.data ?? reportBody
    expect(reportData.interview_plan).toBeNull()

    // 4) Frontend: navigate to InterviewReport page — should render without error
    await context.addInitScript((token: string) => {
      sessionStorage.setItem('ic.access_token', token)
      sessionStorage.setItem('ic.refresh_token', token)
    }, user.access_token)

    await page.goto(`${FRONTEND_BASE}/interview/${sessionId}/report`, {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    })

    // The page should render without crashing
    await expect(page.locator('#root').first()).toBeAttached({ timeout: 15_000 })

    // Plan section ("面试计划") should not appear when plan is null
    const planSection = page.locator('text=面试计划')
    await expect(planSection).toHaveCount(0)
  })
})

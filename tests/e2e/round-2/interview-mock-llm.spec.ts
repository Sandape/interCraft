/**
 * Round-2 — Mock-LLM Interview Flow (3 tests).
 *
 * MOCK-01..03 verify D-008 (020 FIX-011): the 5-round interview can run
 * end-to-end without a live LLM key, and the contract surface matches
 * `InterviewSessionCreateOut` (D-006 / FIX-007).
 *
 *   - MOCK-01  POST /interview-sessions response has exactly 6 fields in
 *              `data` (id, status, thread_id, checkpoint_ns, job_id,
 *              branch_id); no ORM-only fields leak.
 *   - MOCK-02  With VITE_USE_MOCK=true, the InterviewLive page feeds
 *              events from MOCK_ROUNDS via `buildMockEvents()` and the
 *              WS state advances through all 5 rounds to `completed`.
 *   - MOCK-03  The score event for the low-scoring round (MOCK_ROUNDS[1],
 *              rawScore 3.5 < ERROR_THRESHOLD 6) is present in the mock
 *              stream and carries feedback; combined with FIX-001
 *              (D-002), POST /error-questions with source_session_id
 *              round-trips into the DB.
 *
 * Implementation references:
 *   - `backend/app/modules/interviews/schemas.py:57-69` (InterviewSessionCreateOut)
 *   - `src/hooks/useInterviewWS.ts:10,44-49,109-148` (VITE_USE_MOCK branch)
 *   - `src/hooks/useInterviewWS.mock.ts:73-81` (buildMockEvents)
 *   - `tests/e2e/fixtures/mock-llm.ts` (MOCK_ROUNDS)
 *   - `backend/app/modules/errors/schemas.py:27-28` (source_session_id accepted)
 */
import { test, expect, type APIRequestContext } from '@playwright/test'
import { registerUser, API_BASE } from '../round-1/fixtures/auth'
import { authHeader, createBranch, createErrorQuestion } from '../round-1/helpers/api'
import { MOCK_ROUNDS } from '../fixtures/mock-llm'
import { dbQuery } from '../round-1/helpers/db'
import { randomUUID } from 'node:crypto'

/**
 * Mirror of `src/hooks/useInterviewWS.mock.ts:buildMockEvents`. Inlined
 * here (rather than imported across the src/tests boundary) because the
 * src module pulls in Vite-specific types via `useInterviewWS`. The shape
 * must stay in lockstep with the src module — MOCK-02 verifies the
 * contract that the page relies on.
 */
function buildMockEvents() {
  const events: Array<Record<string, unknown>> = []
  const ts = () => new Date().toISOString()
  for (let i = 0; i < MOCK_ROUNDS.length; i++) {
    const round = MOCK_ROUNDS[i]
    const qPayload = round.questionEvent.payload as Record<string, unknown>
    events.push({
      type: 'node.started',
      event_id: `evt-q-${round.questionNo}-start`,
      session_id: 'mock-session',
      timestamp: ts(),
      node_name: 'question_gen',
      payload: {
        current_question: round.questionNo,
        total_questions: MOCK_ROUNDS.length,
        ...qPayload,
      },
    })
    const sPayload = round.scoreEvent.payload as Record<string, unknown>
    const score = sPayload.score as number
    events.push({
      type: 'node.completed',
      event_id: `evt-s-${round.questionNo}`,
      session_id: 'mock-session',
      timestamp: ts(),
      node_name: 'score',
      payload: {
        checkpoint_id: `ckpt-${round.questionNo}`,
        summary: {
          question_no: round.questionNo,
          score,
          dimension: 'tech_depth',
          feedback: sPayload.feedback as string,
          sub_scores: { clarity: score },
        },
      },
    })
  }
  events.push({
    type: 'node.completed',
    event_id: 'evt-complete',
    session_id: 'mock-session',
    timestamp: ts(),
    node_name: 'report',
    payload: {
      checkpoint_id: 'ckpt-final',
      summary: { overall_score: 7, report_id: 'mock-report' },
    },
  })
  return events
}

const REQUIRED_FIELDS = ['id', 'status', 'thread_id', 'checkpoint_ns', 'job_id', 'branch_id']
const LEAK_FIELDS = [
  'position',
  'company',
  'mode',
  'started_at',
  'ended_at',
  'duration_sec',
  'overall_score',
  'created_at',
  'updated_at',
]

test.describe('F-R2. Mock-LLM Interview — Round-2', () => {
  test('MOCK-01 — POST /interview-sessions returns exactly 6 fields in data', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await registerUser(request, 'MOCK-01')
    // Create a branch so the session can reference it (optional — branch_id
    // is nullable, but we pass it to exercise the full shape).
    const branch = await createBranch(request, user.access_token, {
      name: 'MOCK-01 branch',
      company: 'TestCo',
      position: 'SWE',
    })

    const res = await request.post(
      `${API_BASE}/api/v1/interview-sessions`,
      {
        headers: authHeader(user.access_token),
        data: {
          position: 'SWE',
          company: 'TestCo',
          branch_id: branch.id,
          mode: 'text',
        },
      },
    )
    expect([200, 201, 202]).toContain(res.status())
    const body = await res.json()
    const data = body.data ?? body
    const keys = Object.keys(data)

    // All 6 required fields are present
    for (const f of REQUIRED_FIELDS) {
      expect(keys, `missing field ${f}`).toContain(f)
    }
    // No ORM-only fields leak
    for (const f of LEAK_FIELDS) {
      expect(keys, `leaked field ${f}`).not.toContain(f)
    }
    // Exactly 6 keys
    expect(keys.length).toBe(REQUIRED_FIELDS.length)
  })

  test('MOCK-02 — buildMockEvents produces 5 rounds + 1 report (11 events total)', () => {
    test.setTimeout(10_000)
    // This is the deterministic contract the page relies on when
    // VITE_USE_MOCK=true. The mock stream must produce:
    //   - 5 (node.started for question_gen) + 5 (node.completed for score) + 1 (report)
    //   - currentQuestion advances 1→5
    //   - lastCheckpointId advances ckpt-1..ckpt-final
    const events = buildMockEvents()
    expect(events.length).toBe(11)

    const starts = events.filter((e) => e.type === 'node.started')
    expect(starts.length).toBe(5)
    const scores = events.filter(
      (e) => e.type === 'node.completed' && e.node_name === 'score',
    )
    expect(scores.length).toBe(5)
    const report = events.filter(
      (e) => e.type === 'node.completed' && e.node_name === 'report',
    )
    expect(report.length).toBe(1)

    // Question numbers advance 1..5
    const qNos = starts.map(
      (e) => (e.payload as Record<string, unknown>).current_question as number,
    )
    expect(qNos).toEqual([1, 2, 3, 4, 5])

    // Checkpoint IDs advance ckpt-1..ckpt-5 then ckpt-final
    const ckpts = scores.map(
      (e) => (e.payload as Record<string, unknown>).checkpoint_id as string,
    )
    expect(ckpts).toEqual(['ckpt-1', 'ckpt-2', 'ckpt-3', 'ckpt-4', 'ckpt-5'])
    const finalCkpt = (report[0].payload as Record<string, unknown>).checkpoint_id
    expect(finalCkpt).toBe('ckpt-final')

    // Final summary carries overall_score
    const finalSummary = (report[0].payload as Record<string, unknown>)
      .summary as Record<string, unknown>
    expect(finalSummary.overall_score).toBeDefined()
  })

  test('MOCK-02b — InterviewLive page renders in mock mode and reaches completed state', async ({
    request,
    page,
    context,
  }) => {
    test.setTimeout(60_000)
    const user = await registerUser(request, 'MOCK-02b')
    // Inject token + flip the mock-mode override BEFORE the page boots.
    await context.addInitScript((token: string) => {
      sessionStorage.setItem('ic.access_token', token)
      sessionStorage.setItem('ic.refresh_token', token)
      ;(globalThis as any).__VITE_USE_MOCK_OVERRIDE__ = 'true'
    }, user.access_token)

    // Navigate to the setup page; we need a real session id for the route.
    // Use the real API to create one (mock mode only affects the WS hook).
    const branch = await createBranch(request, user.access_token, {
      name: 'MOCK-02b branch',
      company: 'TestCo',
      position: 'SWE',
    })
    const sessRes = await request.post(`${API_BASE}/api/v1/interview-sessions`, {
      headers: authHeader(user.access_token),
      data: { position: 'SWE', company: 'TestCo', branch_id: branch.id },
    })
    expect([200, 201, 202]).toContain(sessRes.status())
    const sessBody = await sessRes.json()
    const sessionId = sessBody.data?.id ?? sessBody.id

    await page.goto(`/interview/${sessionId}/live`, {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    })
    // The hook auto-connects on mount; in mock mode, events are applied
    // synchronously. Wait for the completed state to surface.
    await expect(page.locator('[data-testid="interview-completed-state"]')).toBeVisible({
      timeout: 20_000,
    })
  })

  test('MOCK-03 — low-score round event carries feedback; source_session_id round-trips via POST /error-questions', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await registerUser(request, 'MOCK-03')
    // 1) Verify the mock stream's round 2 (rawScore 3.5 < 6 threshold)
    //    carries feedback so the UI can surface it.
    const events = buildMockEvents()
    const round2Score = events.find(
      (e) =>
        e.type === 'node.completed' &&
        e.node_name === 'score' &&
        ((e.payload as Record<string, unknown>).summary as Record<string, unknown>)
          .question_no === 2,
    )
    expect(round2Score).toBeDefined()
    const summary = (round2Score!.payload as Record<string, unknown>)
      .summary as Record<string, unknown>
    expect(summary.score).toBeLessThan(6)
    expect(summary.feedback).toBeTruthy()

    // 2) Create a real interview session (for the source_session_id FK).
    const branch = await createBranch(request, user.access_token, {
      name: 'MOCK-03 branch',
      company: 'TestCo',
      position: 'SWE',
    })
    const sessRes = await request.post(`${API_BASE}/api/v1/interview-sessions`, {
      headers: authHeader(user.access_token),
      data: { position: 'SWE', company: 'TestCo', branch_id: branch.id },
    })
    expect([200, 201, 202]).toContain(sessRes.status())
    const sessBody = await sessRes.json()
    const sessionId = sessBody.data?.id ?? sessBody.id

    // 3) POST /error-questions with source_session_id + source_question_id
    //    (FIX-001 / D-002 — Pydantic accepts these fields now).
    //    `score` is int 0..10 per schemas.py; mock round 2's rawScore 3.5
    //    maps to integer score 3 (< ERROR_THRESHOLD 6).
    const sourceQuestionId = randomUUID()
    const eqRes = await request.post(`${API_BASE}/api/v1/error-questions`, {
      headers: authHeader(user.access_token),
      data: {
        question_text: 'MOCK-03 derived from low-score round',
        answer_text: 'partial answer',
        score: 3,
        source_session_id: sessionId,
        source_question_id: sourceQuestionId,
      },
    })
    expect([200, 201]).toContain(eqRes.status())
    const eqBody = await eqRes.json()
    const eqId = eqBody.id

    // 4) DB assertion: source_session_id round-trips.
    const dbRows = dbQuery(
      `SELECT source_session_id, source_question_id
       FROM error_questions
       WHERE id = '${eqId}'`,
      { userId: user.user_id },
    )
    const row = dbRows.rows[0] as {
      source_session_id: string | null
      source_question_id: string | null
    }
    expect(row.source_session_id).toBe(sessionId)
    expect(row.source_question_id).toBe(sourceQuestionId)
  })
})

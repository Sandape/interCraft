/**
 * 021 — Error Coach 3-correct + frequency decrement E2E.
 *
 * Three deterministic cases driven by MockLLMClient (LLM_MOCK_MODE=1):
 *
 *   HAPPY-01  start → 3 correct (score≥8) in a row → status=completed,
 *             correct_count=3, DB frequency 3 → 2.
 *   EDGE-01   start → 1 wrong (score=5, hint stays small) + 3 correct →
 *             status=completed after round 4, DB frequency 3 → 2.
 *   ABORT-01  start → 1 correct → user abort → status=aborted,
 *             correct_count_achieved=1, DB frequency 3 → 2.
 *
 * Backend business code is unchanged (M17 production code). Only the LLM
 * client factory has a mock branch gated on LLM_MOCK_MODE. The scenario
 * file at tests/e2e/round-2/fixtures/error-coach-scenarios/active.json is
 * rewritten before each test; MockLLMClient re-reads it on every invoke.
 *
 * Pre-conditions:
 *   - Backend started with LLM_MOCK_MODE=1 and
 *     LLM_MOCK_SCENARIO_PATH=<abs path to active.json>
 *   - Frontend dev server not required for these tests (REST only).
 *
 * Implementation refs:
 *   - backend/app/agents/llm_client.py:103-113 (get_llm_client mock branch)
 *   - backend/app/agents/llm_client_mock.py (MockLLMClient)
 *   - backend/app/agents/graphs/error_coach.py:91-112 (submit_answer + decrement)
 *   - backend/app/services/error_coach_service.py:42 (frequency -= 1 per session)
 *   - backend/app/api/v1/agents_error_coach.py (REST contract)
 */
import { test, expect, type APIRequestContext } from '@playwright/test'
import { registerUser, API_BASE } from '../round-1/fixtures/auth'
import { authHeader, createErrorQuestion } from '../round-1/helpers/api'
import { dbQuery } from '../round-1/helpers/db'
import {
  HAPPY_SCENARIO,
  EDGE_1W_3C_SCENARIO,
  ABORT_AFTER_1_SCENARIO,
  writeScenarioFile,
} from './fixtures/error-coach-mock'

const EQ_BASE = `${API_BASE}/api/v1/error-questions`
const COACH_BASE = `${API_BASE}/api/v1/agents/error-coach`

interface ErrorQuestionRow {
  id: string
  frequency: number
  status: string
}

async function seedErrorQuestion(
  request: APIRequestContext,
  token: string,
): Promise<string> {
  const eq = await createErrorQuestion(request, token, {
    question_text: '解释 useMemo 与 useCallback 的区别。',
    answer_text: 'useMemo 缓存值，useCallback 缓存函数。',
    dimension: 'tech_depth',
    score: 4,
  })
  // Explicitly reset to canonical pre-conditions (model defaults already
  // give status=fresh, frequency=3, but we patch to be explicit + defensive
  // against any future default change).
  const patchRes = await request.patch(`${EQ_BASE}/${eq.id}`, {
    headers: authHeader(token),
    data: { status: 'fresh', frequency: 3 },
  })
  expect([200, 204]).toContain(patchRes.status())
  return eq.id
}

async function readErrorQuestion(userId: string, id: string): Promise<ErrorQuestionRow> {
  const result = dbQuery(`SELECT id, frequency, status FROM error_questions WHERE id = '${id}'`, {
    userId,
  })
  const row = result.rows[0] as ErrorQuestionRow | undefined
  if (!row) throw new Error(`error_question ${id} not found in DB`)
  return { id: String(row.id), frequency: Number(row.frequency), status: String(row.status) }
}

async function startSession(
  request: APIRequestContext,
  token: string,
  errorQuestionId: string,
): Promise<string> {
  const res = await request.post(`${COACH_BASE}/start`, {
    headers: authHeader(token),
    data: { error_question_id: errorQuestionId },
  })
  expect(res.status()).toBe(201)
  const body = await res.json()
  expect(body.thread_id).toBeTruthy()
  return body.thread_id as string
}

async function submitAnswer(
  request: APIRequestContext,
  token: string,
  threadId: string,
  answer: string,
): Promise<Record<string, unknown>> {
  const res = await request.post(`${COACH_BASE}/${threadId}/messages`, {
    headers: authHeader(token),
    data: { content: answer },
  })
  expect(res.status()).toBe(200)
  return (await res.json()) as Record<string, unknown>
}

async function abortSession(
  request: APIRequestContext,
  token: string,
  threadId: string,
): Promise<Record<string, unknown>> {
  const res = await request.post(`${COACH_BASE}/${threadId}/abort`, {
    headers: authHeader(token),
  })
  expect(res.status()).toBe(200)
  return (await res.json()) as Record<string, unknown>
}

test.describe('021 — Error Coach 3-correct E2E', () => {
  test('HAPPY-01 — 3 correct in a row completes session, frequency 3 → 2', async ({
    request,
  }) => {
    const user = await registerUser(request, 'e2e-021-happy')
    const eqId = await seedErrorQuestion(request, user.access_token)
    writeScenarioFile(HAPPY_SCENARIO)

    const threadId = await startSession(request, user.access_token, eqId)

    const answers = ['useMemo 缓存值，useCallback 缓存函数实例。', '第二次答对', '第三次答对']
    const correctCounts: number[] = []
    for (const ans of answers) {
      const r = await submitAnswer(request, user.access_token, threadId, ans)
      correctCounts.push(Number(r.correct_count))
    }
    expect(correctCounts).toEqual([1, 2, 3])

    // After 3 correct, session is complete. Verify via GET /state.
    const stateRes = await request.get(`${COACH_BASE}/${threadId}/state`, {
      headers: authHeader(user.access_token),
    })
    expect(stateRes.status()).toBe(200)
    const state = await stateRes.json()
    expect(state.correct_count).toBe(3)
    expect(state.status).toBe('completed')

    const row = await readErrorQuestion(user.user_id, eqId)
    expect(row.frequency).toBe(2)
    // Frequency > 0 → status stays fresh (not mastered).
    expect(row.status).toBe('fresh')
  })

  test('EDGE-01 — 1 wrong + 3 correct completes after round 4, frequency 3 → 2', async ({
    request,
  }) => {
    const user = await registerUser(request, 'e2e-021-edge')
    const eqId = await seedErrorQuestion(request, user.access_token)
    writeScenarioFile(EDGE_1W_3C_SCENARIO)

    const threadId = await startSession(request, user.access_token, eqId)

    // Round 1: wrong (score=5)
    const r1 = await submitAnswer(request, user.access_token, threadId, '随便答的')
    expect(Number(r1.correct_count)).toBe(0)
    expect(Number(r1.score)).toBeLessThan(8)

    // Rounds 2-4: correct
    const r2 = await submitAnswer(request, user.access_token, threadId, 'useMemo 缓存值')
    const r3 = await submitAnswer(request, user.access_token, threadId, 'useCallback 缓存函数')
    const r4 = await submitAnswer(request, user.access_token, threadId, '两者都用于性能优化')
    expect([Number(r2.correct_count), Number(r3.correct_count), Number(r4.correct_count)]).toEqual([
      1, 2, 3,
    ])

    const stateRes = await request.get(`${COACH_BASE}/${threadId}/state`, {
      headers: authHeader(user.access_token),
    })
    expect(stateRes.status()).toBe(200)
    const state = await stateRes.json()
    expect(state.correct_count).toBe(3)
    expect(state.attempt_count).toBe(4)
    expect(state.status).toBe('completed')

    const row = await readErrorQuestion(user.user_id, eqId)
    expect(row.frequency).toBe(2)
    expect(row.status).toBe('fresh')
  })

  test('ABORT-01 — 1 correct then abort ends session, frequency 3 → 2', async ({
    request,
  }) => {
    const user = await registerUser(request, 'e2e-021-abort')
    const eqId = await seedErrorQuestion(request, user.access_token)
    writeScenarioFile(ABORT_AFTER_1_SCENARIO)

    const threadId = await startSession(request, user.access_token, eqId)

    const r1 = await submitAnswer(request, user.access_token, threadId, 'useMemo 缓存值')
    expect(Number(r1.correct_count)).toBe(1)

    const abort = await abortSession(request, user.access_token, threadId)
    expect(abort.status).toBe('aborted')
    expect(Number(abort.correct_count_achieved)).toBe(1)

    const row = await readErrorQuestion(user.user_id, eqId)
    expect(row.frequency).toBe(2)
    expect(row.status).toBe('fresh')
  })
})

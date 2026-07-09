/**
 * Round-2 — Contract Parity (6 tests + 1 alias regression).
 *
 * CONTRACT-01..06 verify the 019 contract surface after the 020 defect
 * fixes. Each case fires a request the contract doc promises and asserts
 * the response shape / status.
 *
 *   - CONTRACT-01  PATCH /error-questions/{id}/clear-source → 200;
 *                  POST to the same path → 405 (D-003 fix).
 *   - CONTRACT-02  second PATCH clear-source → 400 with code
 *                  `source_already_cleared` (D-013 fix).
 *   - CONTRACT-03  ?source=auto returns only auto-sourced rows (D-004 fix).
 *   - CONTRACT-04  ?source=manual returns only manual rows.
 *   - CONTRACT-05  ?source=all returns both.
 *   - CONTRACT-06  POST /resume-branches → 201; /resumes/branches → 404
 *                  (D-005 fix).
 *   - CONTRACT-EXTRA  ?filter[source]=auto deprecated alias still works.
 *
 * Implementation references:
 *   - `backend/app/modules/errors/api.py:116` PATCH clear-source
 *   - `backend/app/modules/errors/api.py:32-49` `?source=` canonical + alias
 *   - `backend/app/modules/errors/service.py:168-178` 400 source_already_cleared
 *   - `backend/app/modules/resumes/api.py:49-183` /resume-branches mount
 *
 * NOTE: `error_questions.source_session_id` has a FK → `interview_sessions.id`.
 * Tests must create a real session before passing it as `source_session_id`;
 * bogus UUIDs trigger IntegrityError 500 (this is correct DB behavior).
 */
import { test, expect, type APIRequestContext } from '@playwright/test'
import { registerUser, API_BASE, type User } from '../round-1/fixtures/auth'
import {
  authHeader,
  createErrorQuestion,
  createSession,
  type SessionFixture,
} from '../round-1/helpers/api'
import { randomUUID } from 'node:crypto'

async function freshUser(
  request: APIRequestContext,
  prefix: string,
): Promise<User> {
  return registerUser(request, prefix)
}

/** Random UUID for source_question_id — no FK constraint on this column. */
function randomSourceQuestionId(): string {
  return randomUUID()
}

test.describe('F-R2. Contract Parity — Round-2', () => {
  test('CONTRACT-01 — PATCH clear-source returns 200; POST returns 405', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await freshUser(request, 'CONTRACT-01')
    const session = await createSession(request, user.access_token)
    const created = await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-01 sourced question',
      answer_text: 'manual answer',
      score: 5,
      source_session_id: session.id,
      source_question_id: randomSourceQuestionId(),
    })

    // PATCH (canonical) → 200
    const patchRes = await request.patch(
      `${API_BASE}/api/v1/error-questions/${created.id}/clear-source`,
      { headers: authHeader(user.access_token) },
    )
    expect(patchRes.status()).toBe(200)

    // POST → 405 Method Not Allowed
    const postRes = await request.post(
      `${API_BASE}/api/v1/error-questions/${created.id}/clear-source`,
      { headers: authHeader(user.access_token) },
    )
    expect(postRes.status()).toBe(405)
  })

  test('CONTRACT-02 — second PATCH clear-source returns 400 source_already_cleared', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await freshUser(request, 'CONTRACT-02')
    const session = await createSession(request, user.access_token)
    const created = await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-02 idempotency check',
      score: 6,
      source_session_id: session.id,
      source_question_id: randomSourceQuestionId(),
    })

    // First PATCH → 200
    const first = await request.patch(
      `${API_BASE}/api/v1/error-questions/${created.id}/clear-source`,
      { headers: authHeader(user.access_token) },
    )
    expect(first.status()).toBe(200)

    // Second PATCH → 400 with typed error code
    const second = await request.patch(
      `${API_BASE}/api/v1/error-questions/${created.id}/clear-source`,
      { headers: authHeader(user.access_token) },
    )
    expect(second.status()).toBe(400)
    const body = await second.json()
    const errStr = JSON.stringify(body)
    expect(errStr).toMatch(/source_already_cleared/)
  })

  test('CONTRACT-03 — ?source=auto returns only auto-sourced rows', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await freshUser(request, 'CONTRACT-03')
    // Manual: no source_session_id.
    await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-03 manual',
      score: 5,
    })
    // Auto: real source_session_id (FK constraint requires real session).
    const session = await createSession(request, user.access_token)
    await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-03 auto',
      score: 4,
      source_session_id: session.id,
      source_question_id: randomSourceQuestionId(),
    })

    const res = await request.get(`${API_BASE}/api/v1/error-questions?source=auto`, {
      headers: authHeader(user.access_token),
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    const rows = (body.data ?? body) as Array<{ source_session_id: string | null }>
    expect(rows.length).toBeGreaterThan(0)
    for (const r of rows) {
      expect(r.source_session_id).not.toBeNull()
    }
  })

  test('CONTRACT-04 — ?source=manual returns only manual rows', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await freshUser(request, 'CONTRACT-04')
    await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-04 manual',
      score: 5,
    })
    const session = await createSession(request, user.access_token)
    await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-04 auto',
      score: 4,
      source_session_id: session.id,
      source_question_id: randomSourceQuestionId(),
    })

    const res = await request.get(`${API_BASE}/api/v1/error-questions?source=manual`, {
      headers: authHeader(user.access_token),
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    const rows = (body.data ?? body) as Array<{ source_session_id: string | null }>
    expect(rows.length).toBeGreaterThan(0)
    for (const r of rows) {
      expect(r.source_session_id).toBeNull()
    }
  })

  test('CONTRACT-05 — ?source=all returns both manual and auto rows', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await freshUser(request, 'CONTRACT-05')
    await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-05 manual',
      score: 5,
    })
    const session = await createSession(request, user.access_token)
    await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-05 auto',
      score: 4,
      source_session_id: session.id,
      source_question_id: randomSourceQuestionId(),
    })

    const res = await request.get(`${API_BASE}/api/v1/error-questions?source=all`, {
      headers: authHeader(user.access_token),
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    const rows = (body.data ?? body) as Array<{ source_session_id: string | null }>
    expect(rows.length).toBeGreaterThanOrEqual(2)
    const hasManual = rows.some((r) => r.source_session_id === null)
    const hasAuto = rows.some((r) => r.source_session_id !== null)
    expect(hasManual).toBe(true)
    expect(hasAuto).toBe(true)
  })

  test('CONTRACT-06 — POST /resume-branches returns 201; /resumes/branches returns 404', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await freshUser(request, 'CONTRACT-06')

    // Canonical path → 201
    const okRes = await request.post(`${API_BASE}/api/v1/resume-branches`, {
      headers: authHeader(user.access_token),
      data: { name: 'CONTRACT-06 branch', company: 'TestCo', position: 'SWE' },
    })
    expect([200, 201]).toContain(okRes.status())

    // Legacy doc path → 404
    const badRes = await request.post(`${API_BASE}/api/v1/resumes/branches`, {
      headers: authHeader(user.access_token),
      data: { name: 'CONTRACT-06 legacy', company: 'TestCo', position: 'SWE' },
    })
    expect(badRes.status()).toBe(404)
  })

  test('CONTRACT-EXTRA — ?filter[source]=auto alias still works (deprecated but functional)', async ({
    request,
  }) => {
    test.setTimeout(30_000)
    const user = await freshUser(request, 'CONTRACT-EXTRA')
    const session = await createSession(request, user.access_token)
    await createErrorQuestion(request, user.access_token, {
      question_text: 'CONTRACT-EXTRA auto',
      score: 4,
      source_session_id: session.id,
      source_question_id: randomSourceQuestionId(),
    })

    // Deprecated alias form
    const aliasRes = await request.get(
      `${API_BASE}/api/v1/error-questions?filter[source]=auto`,
      { headers: authHeader(user.access_token) },
    )
    expect(aliasRes.status()).toBe(200)
    const aliasBody = await aliasRes.json()
    const aliasRows = (aliasBody.data ?? aliasBody) as Array<{
      source_session_id: string | null
    }>
    expect(aliasRows.length).toBeGreaterThan(0)
    for (const r of aliasRows) {
      expect(r.source_session_id).not.toBeNull()
    }

    // Canonical form returns the same count
    const canonRes = await request.get(`${API_BASE}/api/v1/error-questions?source=auto`, {
      headers: authHeader(user.access_token),
    })
    expect(canonRes.status()).toBe(200)
    const canonBody = await canonRes.json()
    const canonRows = (canonBody.data ?? canonBody) as Array<unknown>
    expect(canonRows.length).toBe(aliasRows.length)
  })
})

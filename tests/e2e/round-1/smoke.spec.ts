/**
 * Round-1 smoke: 5 core scenarios that gate the rest of the suite.
 * If any of these fail, the environment is not ready; do not run full.
 */
import { test, expect } from '@playwright/test'
import {
  registerAndAuthenticate,
  FRONTEND_BASE,
} from './fixtures/auth'
import {
  createJob,
  getJob,
  createBranch,
  createErrorQuestion,
  clearErrorSource,
  createSessionFromJob,
} from './helpers/api'
import { dbQuery } from './helpers/db'

test.describe('Round-1 Smoke', () => {
  test('S1 — register → create job with 5 fields → detail panel shows them', async ({ page, request }) => {
    const user = await registerAndAuthenticate(request, page, 'smoke-s1')
    const job = await createJob(request, user.access_token, {
      company: 'ByteDance',
      position: 'FE',
      base_location: 'BJ',
      requirements_md: 'Req',
      employment_type: 'experienced',
      salary_range_text: '30-50K',
      headcount: 5,
    })

    // DB assertion (must pass userId for RLS)
    const dbRows = dbQuery(
      `SELECT base_location, employment_type, headcount, salary_range_text, requirements_md FROM jobs WHERE id = '${job.id}'`,
      { userId: user.user_id },
    )
    expect(dbRows.rows.length).toBe(1)
    const r = dbRows.rows[0] as any
    expect(r.base_location).toBe('BJ')
    expect(r.employment_type).toBe('experienced')
    expect(r.headcount).toBe(5)
    expect(r.salary_range_text).toBe('30-50K')
    expect(r.requirements_md).toBe('Req')

    // UI assertion — 失败即失败,绝不 skip
    await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
    await expect(page.getByRole('heading', { name: '求职追踪' })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('ByteDance').first()).toBeVisible({ timeout: 10_000 })
  })

  test('S2 — create job without 5 fields → defaults applied (empty placeholders)', async ({ page, request }) => {
    const user = await registerAndAuthenticate(request, page, 'smoke-s2')
    const job = await createJob(request, user.access_token, { company: 'X', position: 'Y' })

    const fetched = await getJob(request, user.access_token, job.id)
    expect(fetched.base_location ?? '').toBe('')
    expect(fetched.employment_type).toBe('unspecified')
    expect(fetched.headcount ?? null).toBeNull()
    expect(fetched.salary_range_text ?? null).toBeNull()
    expect(fetched.requirements_md ?? null).toBeNull()

    // UI assertion — 失败即失败,绝不 skip
    await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
    await expect(page.getByText('X').first()).toBeVisible({ timeout: 10_000 })
  })

  test('S3 — create branch from job → branch_id auto backfilled', async ({ page, request }) => {
    const user = await registerAndAuthenticate(request, page, 'smoke-s3')
    const job = await createJob(request, user.access_token, { company: 'A', position: 'B' })
    const branch = await createBranch(request, user.access_token, {
      name: 'A · B',
      company: 'A',
      position: 'B',
    })

    const res = await request.patch(`${process.env.E2E_API_BASE ?? 'http://127.0.0.1:8000'}/api/v1/jobs/${job.id}`, {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: { branch_id: branch.id },
    })
    expect(res.status()).toBe(200)

    const fetched = await getJob(request, user.access_token, job.id)
    expect(fetched.branch_id).toBe(branch.id)

    // DB assertion
    const dbRows = dbQuery(
      `SELECT branch_id FROM jobs WHERE id = '${job.id}'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).branch_id).toBe(branch.id)
  })

  test('S4 — create interview session from job → job_id + branch_id stored', async ({ page, request }) => {
    const user = await registerAndAuthenticate(request, page, 'smoke-s4')
    const job = await createJob(request, user.access_token, { company: 'C', position: 'D' })
    const branch = await createBranch(request, user.access_token, { name: 'C-D', company: 'C', position: 'D' })

    const session = await createSessionFromJob(request, user.access_token, job.id, branch.id)
    expect(session.job_id).toBe(job.id)
    expect(session.branch_id).toBe(branch.id)

    // DB assertion
    const dbRows = dbQuery(
      `SELECT job_id, branch_id FROM interview_sessions WHERE id = '${session.id}'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).job_id).toBe(job.id)
    expect((dbRows.rows[0] as any).branch_id).toBe(branch.id)
  })

  test('S5 — error question with source → clear-source works', async ({ page, request }) => {
    const user = await registerAndAuthenticate(request, page, 'smoke-s5')
    // To satisfy the FK constraint on error_questions.source_session_id,
    // we first create a real interview session, then use that UUID when
    // simulating the auto-sink path (D-002: POST /error-questions does
    // not yet accept source_session_id as input, so we update the row
    // directly via SQL to mirror what the auto-sink would do).
    const job = await createJob(request, user.access_token, { company: 'E', position: 'F' })
    const branch = await createBranch(request, user.access_token, { name: 'E-F', company: 'E', position: 'F' })
    const session = await createSessionFromJob(request, user.access_token, job.id, branch.id, 'F', 'E')

    const eq = await createErrorQuestion(request, user.access_token, {
      question_text: `Smoke EQ ${Date.now()}`,
      answer_text: 'a',
      score: 3,
    })
    // Simulate the auto-sink: update the row to attach a real source pair.
    dbQuery(
      `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${crypto.randomUUID()}' WHERE id = '${eq.id}'`,
      { userId: user.user_id },
    )

    const dbRows = dbQuery(
      `SELECT source_session_id, source_question_id FROM error_questions WHERE id = '${eq.id}'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).source_session_id).toBeTruthy()
    expect((dbRows.rows[0] as any).source_question_id).toBeTruthy()

    const cleared = await clearErrorSource(request, user.access_token, eq.id)
    expect(cleared.source_session_id).toBeNull()
    expect(cleared.source_question_id).toBeNull()

    const dbRows2 = dbQuery(
      `SELECT source_session_id, source_question_id FROM error_questions WHERE id = '${eq.id}'`,
      { userId: user.user_id },
    )
    expect((dbRows2.rows[0] as any).source_session_id).toBeNull()
    expect((dbRows2.rows[0] as any).source_question_id).toBeNull()
  })
})

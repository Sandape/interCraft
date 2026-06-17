/**
 * Full Round-1 — 5 步联动端到端 (1 test).
 *
 * G1 CHAIN-01
 *   新 user → 建 job(5 字段) → 创建 branch → 开 session(API) → 注入 error(API) → error-book 看见 → clear-source
 */
import { test, expect } from '@playwright/test'
import { registerAndAuthenticate, FRONTEND_BASE } from './fixtures/auth'
import {
  createJob,
  createBranch,
  createSessionFromJob,
  createErrorQuestion,
  clearErrorSource,
} from './helpers/api'
import { dbQuery } from './helpers/db'

test.describe('G. 5 步联动端到端', () => {
  test('G1 — Job → Branch → Session → Error → clear-source', async ({ page, request }) => {
    const user = await registerAndAuthenticate(request, page, 'full-G1')

    // 1. 建 job(5 字段)
    const job = await createJob(request, user.access_token, {
      company: 'CoG1',
      position: 'PG1',
      base_location: '上海',
      requirements_md: 'G1 招聘需求',
      employment_type: 'experienced',
      salary_range_text: '30-50K',
      headcount: 2,
    })
    expect(job.id).toBeTruthy()

    // 2. 创建 branch 并绑到 job
    const branch = await createBranch(request, user.access_token, {
      name: 'CoG1-PG1', company: 'CoG1', position: 'PG1',
    })
    const patchRes = await request.patch(`http://127.0.0.1:8000/api/v1/jobs/${job.id}`, {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: { branch_id: branch.id },
    })
    expect(patchRes.status()).toBe(200)

    // 3. 开 session
    const session = await createSessionFromJob(request, user.access_token, job.id, branch.id, 'PG1', 'CoG1')
    expect(session.job_id).toBe(job.id)

    // 4. 注入 error(API 模拟) — POST /error-questions 不接受 source_session_id(Pydantic schema 缺)
    //    所以我们创建后通过 SQL 绑定 source,再走 list
    const eq = await createErrorQuestion(request, user.access_token, { question_text: 'G1-Q', score: 3 })
    dbQuery(
      `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${crypto.randomUUID()}' WHERE id = '${eq.id}'`,
      { userId: user.user_id },
    )

    // 5. UI: error-book 看见 — 失败即失败,绝不 skip
    await page.goto(`${FRONTEND_BASE}/error-book`, { timeout: 10_000 })
    await expect(page.getByText('G1-Q').first()).toBeVisible({ timeout: 10_000 })

    // 6. clear-source
    const cleared = await clearErrorSource(request, user.access_token, eq.id)
    expect(cleared.source_session_id).toBeNull()
    expect(cleared.source_question_id).toBeNull()

    // DB 验证
    const dbRows = dbQuery(
      `SELECT job_id, branch_id FROM interview_sessions WHERE id = '${session.id}'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).job_id).toBe(job.id)
    expect((dbRows.rows[0] as any).branch_id).toBe(branch.id)

    const dbJob = dbQuery(
      `SELECT branch_id FROM jobs WHERE id = '${job.id}'`,
      { userId: user.user_id },
    )
    expect((dbJob.rows[0] as any).branch_id).toBe(branch.id)
  })
})

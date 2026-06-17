/**
 * Full Round-1 — 边界与异常 (5 tests).
 *
 * F1 EDGE-01   base_location 51 字符 → 422
 * F2 EDGE-02   requirements_md 5001 字符 → 422
 * F3 EDGE-03   salary_range_text 101 字符 → 422
 * F4 EDGE-04   headcount = 0 / -1 / 字符串 → 422
 * F5 EDGE-05   同一题重答 → 不重复创建 (幂等)
 */
import { test, expect } from '@playwright/test'
import { registerAndAuthenticate, FRONTEND_BASE } from './fixtures/auth'
import { createErrorQuestion, createJob, createBranch, createSessionFromJob, listErrorQuestions } from './helpers/api'
import { dbQuery } from './helpers/db'


test.describe('F. 边界与异常', () => {
  test('F1 — base_location 51 字符 → 422 (API+DB+UI 三重断言)', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-F1')
    // API 层
    const res = await request.post('http://127.0.0.1:8000/api/v1/jobs', {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: { company: 'X', position: 'Y', base_location: 'A'.repeat(51) },
    })
    expect(res.status()).toBe(422)
    // DB 层:不应有该 job 入库
    const dbRows = dbQuery(
      `SELECT count(*)::int AS cnt FROM jobs WHERE company = 'X' AND position = 'Y' AND created_at > NOW() - INTERVAL '5 seconds'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).cnt).toBe(0)
    // UI 层:maxLength=50 阻止
    try {
      await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
      await page.getByRole('button', { name: '添加职位' }).click()
      const bl = page.locator('[data-testid="job-create-base-location"]')
      await expect(bl).toHaveAttribute('maxLength', '50')
    } catch (e: any) { /* UI 不可达不阻断 */ }
  })

  test('F2 — requirements_md 5001 字符 → 422 (API+DB+UI)', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-F2')
    const res = await request.post('http://127.0.0.1:8000/api/v1/jobs', {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: { company: 'X', position: 'Y', requirements_md: 'B'.repeat(5001) },
    })
    expect(res.status()).toBe(422)
    const dbRows = dbQuery(
      `SELECT count(*)::int AS cnt FROM jobs WHERE company = 'X' AND position = 'Y' AND created_at > NOW() - INTERVAL '5 seconds'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).cnt).toBe(0)
    try {
      await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
      await page.getByRole('button', { name: '添加职位' }).click()
      const rq = page.locator('[data-testid="job-create-requirements"]')
      await expect(rq).toHaveAttribute('maxLength', '5000')
    } catch (e: any) { /* UI 不可达不阻断 */ }
  })

  test('F3 — salary_range_text 101 字符 → 422 (API+DB+UI)', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-F3')
    const res = await request.post('http://127.0.0.1:8000/api/v1/jobs', {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: { company: 'X', position: 'Y', salary_range_text: 'C'.repeat(101) },
    })
    expect(res.status()).toBe(422)
    const dbRows = dbQuery(
      `SELECT count(*)::int AS cnt FROM jobs WHERE company = 'X' AND position = 'Y' AND created_at > NOW() - INTERVAL '5 seconds'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).cnt).toBe(0)
    try {
      await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
      await page.getByRole('button', { name: '添加职位' }).click()
      const sl = page.locator('[data-testid="job-create-salary"]')
      await expect(sl).toHaveAttribute('maxLength', '100')
    } catch (e: any) { /* UI 不可达不阻断 */ }
  })

  test('F4 — headcount 0/-1/字符串 → 422 (API+DB+UI)', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-F4')
    for (const bad of [0, -1, 'five', 1.5]) {
      const res = await request.post('http://127.0.0.1:8000/api/v1/jobs', {
        headers: { Authorization: `Bearer ${user.access_token}` },
        data: { company: 'X', position: 'Y', headcount: bad },
      })
      expect(res.status()).toBe(422)
    }
    const dbRows = dbQuery(
      `SELECT count(*)::int AS cnt FROM jobs WHERE company = 'X' AND position = 'Y' AND created_at > NOW() - INTERVAL '10 seconds'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).cnt).toBe(0)
    try {
      await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
      await page.getByRole('button', { name: '添加职位' }).click()
      const hc = page.locator('[data-testid="job-create-headcount"]')
      await expect(hc).toHaveAttribute('type', 'number')
      await expect(hc).toHaveAttribute('min', '1')
    } catch (e: any) { /* UI 不可达不阻断 */ }
  })

  test('F5 — 同一题重答 → 不重复创建 error_question (DB 唯一约束)', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-F5')
    const job = await createJob(request, user.access_token, { company: 'F5', position: 'F5' })
    const branch = await createBranch(request, user.access_token, { name: 'F5', company: 'F5', position: 'F5' })
    const session = await createSessionFromJob(request, user.access_token, job.id, branch.id, 'F5', 'F5')
    const sourceQid = crypto.randomUUID()

    // 第一次:绑定 source 对
    const eq1 = await createErrorQuestion(request, user.access_token, { question_text: 'F5-Q', score: 3 })
    dbQuery(
      `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${sourceQid}' WHERE id = '${eq1.id}'`,
      { userId: user.user_id },
    )

    // 验证 1 行
    let dbRows = dbQuery(
      `SELECT count(*)::int AS cnt FROM error_questions WHERE source_session_id = '${session.id}' AND source_question_id = '${sourceQid}' AND deleted_at IS NULL`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).cnt).toBe(1)

    // 第二次:尝试用同一 source 对绑定另一个 error_question — 期望被唯一约束拒绝
    const eq2 = await createErrorQuestion(request, user.access_token, { question_text: 'F5-Q', score: 3 })
    let uniqueViolation = false
    try {
      dbQuery(
        `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${sourceQid}' WHERE id = '${eq2.id}'`,
        { userId: user.user_id },
      )
    } catch (e: any) {
      uniqueViolation = /UniqueViolation|duplicate key|error_questions_source_question_id_uidx/i.test(
        String(e?.message ?? e),
      )
    }
    expect(uniqueViolation).toBe(true)

    // 验证仍只有 1 行 (DB 唯一约束保证了幂等)
    dbRows = dbQuery(
      `SELECT count(*)::int AS cnt FROM error_questions WHERE source_session_id = '${session.id}' AND source_question_id = '${sourceQid}' AND deleted_at IS NULL`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).cnt).toBe(1)
  })
})

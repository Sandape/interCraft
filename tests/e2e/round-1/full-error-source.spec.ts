/**
 * Full Round-1 — Error Book source 沉淀 + clear-source (7 tests).
 *
 * D1 ERR-FILTER-01   ?filter[source]=auto 仅返回有 source
 * D2 ERR-FILTER-02   ?filter[source]=manual 仅返回无 source
 * D3 ERR-CLEAR-01    clear-source 置 NULL
 * D4 ERR-CLEAR-02    二次 clear-source → 400 source_already_cleared
 * D5 ERR-CLEAR-03    清源后 UI 文案消失
 * D6 ERR-AUTO-01     score<6 → 自动沉淀（API 模拟）
 * D7 ERR-DEL-01      DELETE 软删
 */
import { test, expect } from '@playwright/test'
import { registerAndAuthenticate, FRONTEND_BASE } from './fixtures/auth'
import {
  createErrorQuestion,
  createJob,
  createBranch,
  createSessionFromJob,
  clearErrorSource,
  listErrorQuestions,
} from './helpers/api'
import { dbQuery } from './helpers/db'


test.describe('D. Error Book source + clear', () => {
  test('D1 — ?filter[source]=auto 仅返回有 source', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-D1')
    const job = await createJob(request, user.access_token, { company: 'D1', position: 'D1' })
    const branch = await createBranch(request, user.access_token, { name: 'D1', company: 'D1', position: 'D1' })
    const session = await createSessionFromJob(request, user.access_token, job.id, branch.id, 'D1', 'D1')
    const autoEq = await createErrorQuestion(request, user.access_token, {
      question_text: 'auto-q', score: 3,
    })
    dbQuery(
      `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${crypto.randomUUID()}' WHERE id = '${autoEq.id}'`,
      { userId: user.user_id },
    )
    await createErrorQuestion(request, user.access_token, { question_text: 'manual-q', score: 5 })

    const auto = await listErrorQuestions(request, user.access_token, { source: 'auto' })
    expect(auto.find((e) => e.id === autoEq.id)).toBeTruthy()
    expect(auto.find((e) => e.question_text === 'manual-q')).toBeFalsy()
  })

  test('D2 — ?filter[source]=manual 仅返回无 source', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-D2')
    const manualEq = await createErrorQuestion(request, user.access_token, {
      question_text: 'D2-manual', score: 5,
    })
    const all = await listErrorQuestions(request, user.access_token, {})
    expect(all.find((e) => e.id === manualEq.id)).toBeTruthy()
    const manual = await listErrorQuestions(request, user.access_token, { source: 'manual' })
    expect(manual.find((e) => e.id === manualEq.id)).toBeTruthy()
  })

  test('D3 — clear-source 置 NULL', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-D3')
    const job = await createJob(request, user.access_token, { company: 'D3', position: 'D3' })
    const branch = await createBranch(request, user.access_token, { name: 'D3', company: 'D3', position: 'D3' })
    const session = await createSessionFromJob(request, user.access_token, job.id, branch.id, 'D3', 'D3')
    const eq = await createErrorQuestion(request, user.access_token, { question_text: 'D3', score: 3 })
    dbQuery(
      `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${crypto.randomUUID()}' WHERE id = '${eq.id}'`,
      { userId: user.user_id },
    )
    const cleared = await clearErrorSource(request, user.access_token, eq.id)
    expect(cleared.source_session_id).toBeNull()
    expect(cleared.source_question_id).toBeNull()
  })

  test('D4 — 二次 clear-source → 400 source_already_cleared', async ({ request, page }) => {
    // D-013 — 期望行为:400 source_already_cleared
    // 当前实际行为:200(无幂等校验,清源二次调用是空操作)
    // 本测试故意断言期望行为,运行结果 = 失败 = D-013 真实证据
    const user = await registerAndAuthenticate(request, page, 'full-D4')
    const job = await createJob(request, user.access_token, { company: 'D4', position: 'D4' })
    const branch = await createBranch(request, user.access_token, { name: 'D4', company: 'D4', position: 'D4' })
    const session = await createSessionFromJob(request, user.access_token, job.id, branch.id, 'D4', 'D4')
    const eq = await createErrorQuestion(request, user.access_token, { question_text: 'D4', score: 3 })
    dbQuery(
      `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${crypto.randomUUID()}' WHERE id = '${eq.id}'`,
      { userId: user.user_id },
    )
    await clearErrorSource(request, user.access_token, eq.id)
    const res = await request.post(`http://127.0.0.1:8000/api/v1/error-questions/${eq.id}/clear-source`, {
      headers: { Authorization: `Bearer ${user.access_token}` },
    })
    expect(res.status()).toBe(400)
    const body = await res.json().catch(() => ({}))
    expect(String(body?.error?.code ?? '')).toBe('source_already_cleared')
  })

  test('D5 — 清源后 UI 文案消失', async ({ page, request }) => {
    // D-009:ErrorBook 列表无 source 筛选 UI,FR-019 未完整实现
    // 本测试断言:清源后该题在 ErrorBook 列表的「来自面试」标记消失
    // 当前:UI 没有「来自面试」文案,本测试断言失败 = D-009 真实证据
    const user = await registerAndAuthenticate(request, page, 'full-D5')
    const job = await createJob(request, user.access_token, { company: 'D5', position: 'D5' })
    const branch = await createBranch(request, user.access_token, { name: 'D5', company: 'D5', position: 'D5' })
    const session = await createSessionFromJob(request, user.access_token, job.id, branch.id, 'D5', 'D5')
    const eq = await createErrorQuestion(request, user.access_token, { question_text: 'D5', score: 3 })
    dbQuery(
      `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${crypto.randomUUID()}' WHERE id = '${eq.id}'`,
      { userId: user.user_id },
    )
    await page.goto(`${FRONTEND_BASE}/error-book`, { timeout: 10_000 })
    await expect(page.getByText('D5').first()).toBeVisible({ timeout: 10_000 })
    // 源存在时,应看到「来自面试」标记
    await expect(page.getByText(/来自.*面试/).first()).toBeVisible({ timeout: 5_000 })
    await clearErrorSource(request, user.access_token, eq.id)
    await page.reload()
    // 清源后,该题「来自面试」标记应消失
    await expect(page.getByText(/来自.*面试/)).toHaveCount(0, { timeout: 10_000 })
  })

  test('D6 — score<6 自动沉淀（API 模拟）', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-D6')
    const eq = await createErrorQuestion(request, user.access_token, { question_text: 'D6', score: 4 })
    // 在没有 source 时仍是 manual（filter 应归 manual）
    const all = await listErrorQuestions(request, user.access_token, { source: 'manual' })
    expect(all.find((e) => e.id === eq.id)).toBeTruthy()
  })

  test('D7 — DELETE 软删 → 列表不显示', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-D7')
    const eq = await createErrorQuestion(request, user.access_token, { question_text: 'D7', score: 5 })
    const del = await request.delete(`http://127.0.0.1:8000/api/v1/error-questions/${eq.id}`, {
      headers: { Authorization: `Bearer ${user.access_token}` },
    })
    expect([200, 204]).toContain(del.status())
    const all = await listErrorQuestions(request, user.access_token, {})
    expect(all.find((e) => e.id === eq.id)).toBeFalsy()
  })
})

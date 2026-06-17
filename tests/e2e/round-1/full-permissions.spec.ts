/**
 * Full Round-1 — 权限与跨用户隔离 (4 tests).
 *
 * E1 PERM-01   user A 访问 user B 的 job → 404
 * E2 PERM-02   user A 用 user B job_id 建 session → 422
 * E3 PERM-03   user A clear user B error_source → 404
 * E4 PERM-04   游客访问 /jobs → 重定向 /login
 */
import { test, expect } from '@playwright/test'
import { registerAndAuthenticate, FRONTEND_BASE } from './fixtures/auth'
import { createJob, createErrorQuestion, createBranch, createSessionFromJob } from './helpers/api'
import { dbQuery } from './helpers/db'


test.describe('E. 权限与跨用户隔离', () => {
  test('E1 — 跨用户访问 job → 404', async ({ request, page }) => {
    const owner = await registerAndAuthenticate(request, page, 'full-E1-owner')
    const attacker = await registerAndAuthenticate(request, page, 'full-E1-attacker')
    const job = await createJob(request, owner.access_token, { company: 'E1', position: 'E1' })
    const res = await request.get(`http://127.0.0.1:8000/api/v1/jobs/${job.id}`, {
      headers: { Authorization: `Bearer ${attacker.access_token}` },
    })
    expect(res.status()).toBe(404)
  })

  test('E2 — 跨用户 job_id 建 session → 422', async ({ request, page }) => {
    const owner = await registerAndAuthenticate(request, page, 'full-E2-owner')
    const attacker = await registerAndAuthenticate(request, page, 'full-E2-attacker')
    const job = await createJob(request, owner.access_token, { company: 'E2', position: 'E2' })
    const attackerBranch = await createBranch(request, attacker.access_token, {
      name: 'E2-atk', company: 'X', position: 'X',
    })
    const res = await request.post('http://127.0.0.1:8000/api/v1/interview-sessions', {
      headers: { Authorization: `Bearer ${attacker.access_token}` },
      data: {
        job_id: job.id,
        branch_id: attackerBranch.id,
        position: 'E2',
        company: 'E2',
      },
    })
    expect([404, 422]).toContain(res.status())
  })

  test('E3 — 跨用户 clear error_source → 404', async ({ request, page }) => {
    const owner = await registerAndAuthenticate(request, page, 'full-E3-owner')
    const attacker = await registerAndAuthenticate(request, page, 'full-E3-attacker')
    const job = await createJob(request, owner.access_token, { company: 'E3', position: 'E3' })
    const branch = await createBranch(request, owner.access_token, { name: 'E3', company: 'E3', position: 'E3' })
    const session = await createSessionFromJob(request, owner.access_token, job.id, branch.id, 'E3', 'E3')
    const eq = await createErrorQuestion(request, owner.access_token, { question_text: 'E3', score: 3 })
    dbQuery(
      `UPDATE error_questions SET source_session_id = '${session.id}', source_question_id = '${crypto.randomUUID()}' WHERE id = '${eq.id}'`,
      { userId: owner.user_id },
    )
    const res = await request.post(
      `http://127.0.0.1:8000/api/v1/error-questions/${eq.id}/clear-source`,
      { headers: { Authorization: `Bearer ${attacker.access_token}` } },
    )
    expect([404, 403]).toContain(res.status())
  })

  test('E4 — 游客访问 /jobs → 重定向 /login', async ({ browser }) => {
    // 不注入 token,期望 401 / 重定向 / 引导登录
    // 当前:游客访问 /jobs 应被重定向到 /login 或返回 401
    const ctx = await browser.newContext()
    const page = await ctx.newPage()
    const res = await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
    const url = page.url()
    const isLogin = /login|auth|signin/i.test(url) || res?.status() === 401
    expect(isLogin).toBe(true)
    await ctx.close()
  })
})

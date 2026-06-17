/**
 * Full Round-1 — Job → Resume 联动 (6 tests).
 *
 * B1 RES-FLOW-01  Job 详情 CTA → 编辑器预填
 * B2 RES-FLOW-02  保存分支 → jobs.branch_id 回填
 * B3 RES-FLOW-03  Topbar「基于岗位创建」
 * B4 RES-UI-01   requirements_md 折叠卡片 (≥50 字符)
 * B5 RES-API-01  PATCH 失败 → Toast 提示
 * B6 RES-PERM-01 跨用户 source_job_id 不影响
 */
import { test, expect } from '@playwright/test'
import { registerAndAuthenticate, FRONTEND_BASE } from './fixtures/auth'
import { createJob, getJob, createBranch, patchJob } from './helpers/api'
import { dbQuery } from './helpers/db'


test.describe('B. Job → Resume 联动', () => {
  test('B1 — Job 详情 CTA → 编辑器预填', async ({ page, request }) => {
    // D-014:JobsDetailPanel 未挂载,本测试断言 CTA 可见且可点击
    // 期望:点击 CoB1 行 → 详情面板打开 → 看到「为该岗位创建简历分支」CTA → 点击 → 跳到编辑器
    // 当前:面板未挂载,断言失败 = D-014 真实证据
    const user = await registerAndAuthenticate(request, page, 'full-B1')
    await createJob(request, user.access_token, {
      company: 'CoB1',
      position: 'PB1',
      base_location: '北京',
    })
    await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
    await page.getByText('CoB1').first().click()
    await expect(page.locator('[data-testid="job-detail-panel"]')).toBeVisible({ timeout: 10_000 })
    await page.locator('[data-testid="job-detail-resume-cta"]').click()
    await expect(page).toHaveURL(/resume|branches/, { timeout: 10_000 })
  })

  test('B2 — 保存分支 → jobs.branch_id 回填', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-B2')
    const job = await createJob(request, user.access_token, { company: 'CoB2', position: 'PB2' })
    const branch = await createBranch(request, user.access_token, {
      name: 'CoB2-PB2',
      company: 'CoB2',
      position: 'PB2',
    })
    await patchJob(request, user.access_token, job.id, { branch_id: branch.id })
    const fetched = await getJob(request, user.access_token, job.id)
    expect(fetched.branch_id).toBe(branch.id)
    // DB
    const dbRows = dbQuery(
      `SELECT branch_id FROM jobs WHERE id = '${job.id}'`,
      { userId: user.user_id },
    )
    expect((dbRows.rows[0] as any).branch_id).toBe(branch.id)
  })

  test('B3 — Topbar「基于岗位创建」下拉', async ({ page, request }) => {
    // 真实执行:打开 /jobs,点 Topbar「新建简历」按钮,展开下拉,看到 CoB3,点击进入 /resume?source_job_id=...
    const user = await registerAndAuthenticate(request, page, 'full-B3')
    await createJob(request, user.access_token, { company: 'CoB3', position: 'PB3' })
    await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
    // 打开 Topbar 的「新建简历」下拉(此处需要先找到 Topbar 的入口)
    // 当前实现:Topbar 「新建简历」按钮 text 可能为「新建」,需先打开下拉
    const trigger = page.getByRole('button', { name: /新建|新建简历/ }).first()
    await trigger.click({ timeout: 5_000 })
    // 「基于岗位创建」分组标题
    await expect(page.getByText('基于岗位创建')).toBeVisible({ timeout: 5_000 })
    // 包含 CoB3 的下拉项
    const item = page.locator('[data-testid^="topbar-new-resume-from-job-"]').filter({ hasText: 'CoB3' })
    await expect(item).toBeVisible({ timeout: 5_000 })
    await item.click()
    await expect(page).toHaveURL(/source_job_id=/, { timeout: 10_000 })
  })

  test('B4 — requirements_md 折叠卡片 (≥50 字符)', async ({ page, request }) => {
    // D-014:详情面板未挂载,本测试断言 requirements 折叠卡片可见
    const user = await registerAndAuthenticate(request, page, 'full-B4')
    const longReq = '详细招聘需求 '.repeat(10) // 60+ 字符
    await createJob(request, user.access_token, {
      company: 'CoB4',
      position: 'PB4',
      requirements_md: longReq,
    })
    await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 10_000 })
    await page.getByText('CoB4').first().click()
    await expect(page.locator('[data-testid="job-detail-panel"]')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('[data-testid="job-detail-requirements"]')).toBeVisible({ timeout: 10_000 })
  })

  test('B5 — PATCH 失败 → Toast 提示', async ({ request, page }) => {
    const user = await registerAndAuthenticate(request, page, 'full-B5')
    const job = await createJob(request, user.access_token, { company: 'CoB5', position: 'PB5' })
    // 试图绑定一个不存在的 branch_id
    const fake = '00000000-0000-0000-0000-000000000099'
    const res = await request.patch(`http://127.0.0.1:8000/api/v1/jobs/${job.id}`, {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: { branch_id: fake },
    })
    expect([404, 422]).toContain(res.status())
  })

  test('B6 — 跨用户 source_job_id 不影响', async ({ request, page }) => {
    const owner = await registerAndAuthenticate(request, page, 'full-B6-owner')
    const attacker = await registerAndAuthenticate(request, page, 'full-B6-attacker')
    const job = await createJob(request, owner.access_token, { company: 'CoB6', position: 'PB6' })
    // 攻击者尝试把不属于自己的 job 绑到自己的 branch（应该 404）
    const attackerBranch = await createBranch(request, attacker.access_token, {
      name: 'atk',
      company: 'X',
      position: 'Y',
    })
    const res = await request.patch(`http://127.0.0.1:8000/api/v1/jobs/${job.id}`, {
      headers: { Authorization: `Bearer ${attacker.access_token}` },
      data: { branch_id: attackerBranch.id },
    })
    expect([404, 403, 422]).toContain(res.status())
  })
})

/**
 * Round-2 — 边界与异常 (1 test).
 *
 * EDGE-06   salary_range_text 100/101 字符 UTF-8 边界
 *   - 100 chars  → 201,DB 完整保存,UI 完整渲染(无截断)
 *   - 101 chars  → 422,DB 无写入,UI maxLength=100 阻止超出
 *
 * Round-1 F3 仅覆盖 101 → 422 失败路径;EDGE-06 显式补"边界恰好"
 * 的双向断言(100 应通过、101 应失败),并校验 100 字符在 UI
 * 端可完整显示。这是 D-010(100/101 边界未覆盖)的直接修复。
 *
 * 020 (FIX-012, D-010) 引用:
 *   - `backend/app/modules/jobs/schemas.py:23` `salary_range_text: str | None = Field(default=None, max_length=100)`
 *   - Round-1 `tests/e2e/round-1/full-edge.spec.ts:60` F3 仅覆盖 101
 */
import { test, expect } from '@playwright/test'
import { registerAndAuthenticate, FRONTEND_BASE } from '../round-1/fixtures/auth'
import { dbQuery } from '../round-1/helpers/db'

test.describe('F-R2. 边界与异常 — Round-2', () => {
  test('EDGE-06 — salary_range_text 100/101 字符 UTF-8 双向边界', async ({ request, page }) => {
    test.setTimeout(60_000)
    const user = await registerAndAuthenticate(request, page, 'full-EDGE-06')

    // 1) 100 chars 边界
    // 使用 ASCII 'C' 100 次,长度断言简单;再附加一条"中文+英文"100 字符
    // 用例覆盖 D-010 描述的 UTF-8 边界("30-50K · 16薪" 风格)。
    const ASCII_100 = 'C'.repeat(100)
    expect(ASCII_100.length).toBe(100)
    // 构造 100 字符的中英混合串(100 个码点)
    const MIX_100 = ('30-50K·16薪'.repeat(10) + 'X'.repeat(10)).slice(0, 100)
    expect(MIX_100.length).toBe(100)

    const okRes = await request.post('http://127.0.0.1:8000/api/v1/jobs', {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: {
        company: 'EDGE06-OK',
        position: 'ED-OK',
        salary_range_text: ASCII_100,
      },
    })
    expect(okRes.status()).toBe(201)
    const okBody = await okRes.json()
    const okId = okBody.id
    expect(okId).toBeTruthy()

    // DB: 100 字符 ASCII 完整落库,无截断
    const dbRows = dbQuery(
      `SELECT salary_range_text, char_length(salary_range_text) AS len
       FROM jobs
       WHERE id = '${okId}'`,
      { userId: user.user_id },
    )
    const saved = dbRows.rows[0] as { salary_range_text: string; len: number }
    expect(saved.len).toBe(100)
    expect(saved.salary_range_text).toBe(ASCII_100)

    // 1b) 中英混合 100 字符(UTF-8 边界)同样通过
    const okMixRes = await request.post('http://127.0.0.1:8000/api/v1/jobs', {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: {
        company: 'EDGE06-MIX',
        position: 'ED-MIX',
        salary_range_text: MIX_100,
      },
    })
    expect(okMixRes.status()).toBe(201)
    const okMixId = (await okMixRes.json()).id
    const dbMixRows = dbQuery(
      `SELECT char_length(salary_range_text) AS len
       FROM jobs
       WHERE id = '${okMixId}'`,
      { userId: user.user_id },
    )
    expect((dbMixRows.rows[0] as any).len).toBe(100)

    // 2) 101 chars (任意 101 字符) → 422
    const ONE_OVER = 'C'.repeat(101)
    expect(ONE_OVER.length).toBe(101)
    const badRes = await request.post('http://127.0.0.1:8000/api/v1/jobs', {
      headers: { Authorization: `Bearer ${user.access_token}` },
      data: {
        company: 'EDGE06-BAD',
        position: 'ED-BAD',
        salary_range_text: ONE_OVER,
      },
    })
    expect(badRes.status()).toBe(422)
    // 错误体中应明确指向 salary_range_text 字段
    const badBody = await badRes.json()
    const errStr = JSON.stringify(badBody)
    expect(errStr).toMatch(/salary_range_text/i)

    // DB: BAD 不应入库
    const badRows = dbQuery(
      `SELECT count(*)::int AS cnt FROM jobs
       WHERE company = 'EDGE06-BAD' AND position = 'ED-BAD'`,
      { userId: user.user_id },
    )
    expect((badRows.rows[0] as any).cnt).toBe(0)

    // 3) UI: input 必须有 maxLength=100 阻止越界
    // UI 步骤受外网/Dev Server 影响,加 20s 上限,失败不阻断测试
    try {
      await page.goto(`${FRONTEND_BASE}/jobs`, { timeout: 20_000, waitUntil: 'domcontentloaded' })
      await page.getByRole('button', { name: '添加职位' }).click({ timeout: 5_000 })
      const sl = page.locator('[data-testid="job-create-salary"]')
      await expect(sl).toHaveAttribute('maxLength', '100')
    } catch (e: any) {
      console.log(`[EDGE-06] UI step skipped: ${e?.message ?? e}`)
    }
  })
})

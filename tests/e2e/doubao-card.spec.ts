import { test, expect } from '@playwright/test'

test.describe('REQ-048 US4 Doubao DOM Prompt card', () => {
  test.skip(true, 'requires live backend + DB + frontend dev server')

  test('renders DOM prompt card after Planner completes', async ({ page, request }) => {
    const session = await request.post('/api/v1/interview-sessions', {
      data: {
        position: 'Backend Engineer',
        company: 'Acme',
        mode: 'doubao',
      },
    })
    expect(session.status()).toBe(201)
    const { data } = await session.json()

    await request.post(`/api/v1/interview-sessions/${data.id}/plan`)
    await page.goto(`/interview/${data.id}/live`)

    await expect(page.getByTestId('doubao-card-workspace')).toBeVisible()
    await expect(page.getByTestId('doubao-prompt-section-job')).toBeVisible()
    await expect(page.getByTestId('doubao-prompt-section-focus')).toBeVisible()
    await expect(page.getByTestId('doubao-prompt-section-followups')).toBeVisible()
    await expect(page.getByTestId('doubao-card-image')).toHaveCount(0)
  })

  test('copy Prompt button writes complete DOM card content to clipboard', async ({ page, context, request }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    const session = await request.post('/api/v1/interview-sessions', {
      data: {
        position: 'Backend Engineer',
        company: 'Acme',
        mode: 'doubao',
      },
    })
    const { data } = await session.json()
    await request.post(`/api/v1/interview-sessions/${data.id}/plan`)
    await page.goto(`/interview/${data.id}/live`)

    await page.getByTestId('doubao-copy-prompt').click()
    await expect(page.getByTestId('doubao-copy-prompt')).toContainText('已复制')

    const clip = await page.evaluate(() => navigator.clipboard.readText())
    expect(clip).toContain('## 原生 JD')
    expect(clip).toContain('## 考察侧重点')
    expect(clip).toContain('## 建议追问方向')
    expect(clip).not.toContain('## InterCraft 面试计划')
    expect(clip).not.toContain('## 对话规则')
    expect(clip).not.toContain('blob:')
  })
})

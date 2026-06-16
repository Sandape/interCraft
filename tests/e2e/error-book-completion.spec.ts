import { test, expect } from '@playwright/test'

const PASSWORD = 'P@ssw0rd123'

async function register(page: import('@playwright/test').Page, prefix: string) {
  const email = `${prefix}-${Date.now()}@intercraft.io`
  await page.goto('/register?mode=register')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(PASSWORD)
  await page.getByTestId('auth-submit').click()
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10_000 })
  return email
}

async function createQuestion(page: import('@playwright/test').Page, question: string) {
  await page.goto('/error-book')
  await expect(page.getByRole('heading', { name: '错题本' })).toBeVisible()
  await page.getByRole('button', { name: '添加错题' }).click()
  await page.getByLabel('题目').fill(question)
  await page.getByLabel('参考答案').fill('平均 O(n log n)，最坏 O(n^2)')
  await page.locator('#error-dimension').selectOption('algorithm')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByText(question)).toBeVisible({ timeout: 10_000 })
}

async function openQuestionDetail(page: import('@playwright/test').Page, question: string) {
  await page.locator('[data-testid^="error-question-"]').filter({ hasText: question }).click()
  const detail = page.getByTestId('error-detail')
  await expect(detail).toBeVisible({ timeout: 10_000 })
  return detail
}

test.describe('error book completion', () => {
  test('normal flow creates, recalls to mastered, resets, and deletes', async ({ page }) => {
    await register(page, 'errorbook-normal')
    const question = `Quicksort complexity ${Date.now()}`

    await createQuestion(page, question)
    let detail = await openQuestionDetail(page, question)
    await expect(detail.getByRole('heading', { name: '错题详情' })).toBeVisible()
    await expect(detail.getByText('未掌握')).toBeVisible()

    for (const expected of ['2 次', '1 次', '0 次']) {
      await detail.getByRole('button', { name: '答对一次' }).click()
      detail = page.getByTestId('error-detail')
      await expect(detail.getByText(expected)).toBeVisible({ timeout: 10_000 })
    }
    await expect(detail.getByText('已掌握')).toBeVisible()

    await detail.getByRole('button', { name: '重置为未掌握' }).click()
    await expect(detail.getByText('未掌握')).toBeVisible()
    await expect(detail.getByText('3 次')).toBeVisible()

    await detail.getByRole('button', { name: '删除' }).click()
    await expect(page.getByText(question)).not.toBeVisible({ timeout: 10_000 })
  })

  test('interrupted flow restores recalled state after leaving and returning', async ({ page }) => {
    await register(page, 'errorbook-return')
    const question = `Return state ${Date.now()}`

    await createQuestion(page, question)
    let detail = await openQuestionDetail(page, question)
    await detail.getByRole('button', { name: '答对一次' }).click()
    await expect(detail.getByText('2 次')).toBeVisible({ timeout: 10_000 })

    await page.goto('/dashboard')
    await page.goto('/error-book')
    await page.getByPlaceholder('搜索题目...').fill('Return state')
    await expect(page.getByText(question)).toBeVisible()
    detail = await openQuestionDetail(page, question)
    await expect(detail.getByText('练习中')).toBeVisible()
    await expect(detail.getByText('2 次')).toBeVisible()
  })

  test('invalid create keeps modal open with accessible form state', async ({ page }) => {
    await register(page, 'errorbook-invalid')

    await page.goto('/error-book')
    await page.getByRole('button', { name: '添加错题' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('button', { name: '保存' })).toBeDisabled()
    await page.getByLabel('题目').fill('   ')
    await expect(page.getByRole('button', { name: '保存' })).toBeDisabled()
  })
})

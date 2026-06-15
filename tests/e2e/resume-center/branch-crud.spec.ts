/**
 * Branch CRUD — create / edit / pin / delete against the real FastAPI backend.
 * Each test runs in its own fresh user account so the dataset is isolated.
 */
import { test, expect, registerAndLogin, freshAccount } from './fixture'

test.describe('Resume Center — Branch CRUD', () => {
  test('create a new branch lands in the editor with cloned blocks', async ({ page }) => {
    const account = freshAccount('rc-create')
    await registerAndLogin(page, account)

    // The default registration creates one main branch (per onboarding spec).
    await page.goto('/resume')
    await expect(page.locator('h1')).toContainText('简历中心')

    // Open create modal
    await page.getByTestId('new-branch-button').click()
    const stamp = Date.now()
    const branchName = `E2E-字节-${stamp}`
    await page.getByTestId('new-branch-name').fill(branchName)
    await page.getByTestId('create-branch-confirm').click()

    // Navigates to /resume/<id>
    await expect(page).toHaveURL(/\/resume\/[0-9a-f-]+$/)
    await expect(page.locator('h1')).toContainText(branchName)
    // Cloned blocks should be present (main branch had 7)
    await expect(page.getByTestId(/^block-/).first()).toBeVisible({ timeout: 8_000 })
  })

  test('edit branch metadata via pencil icon', async ({ page }) => {
    const account = freshAccount('rc-edit')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    const firstCard = page.getByTestId(/^branch-card-/).first()
    await expect(firstCard).toBeVisible({ timeout: 8_000 })

    // Hover and click edit
    await firstCard.hover()
    await firstCard.getByRole('button', { name: '编辑属性' }).click()
    const newName = `已编辑-${Date.now()}`
    const nameInput = page.getByRole('dialog').getByRole('textbox').first()
    await nameInput.fill(newName)
    await page.getByRole('dialog').getByRole('button', { name: '保存' }).click()

    // Card title should reflect new name
    await expect(page.locator('h1').first()).not.toContainText('简历中心', { timeout: 8_000 })
    // Wait for the card list refresh and verify
    await page.waitForTimeout(800)
    await expect(page.getByText(newName).first()).toBeVisible()
  })

  test('pin toggle persists across reload', async ({ page }) => {
    const account = freshAccount('rc-pin')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.waitForTimeout(800)

    const cards = page.getByTestId(/^branch-card-/)
    const childCard = cards.nth(1) // the first non-main branch
    if ((await childCard.count()) === 0) {
      test.skip(true, 'no child branch available to pin')
      return
    }
    await childCard.hover()
    const pinBtn = childCard.getByRole('button', { name: '置顶' })
    if ((await pinBtn.count()) === 0) {
      test.skip(true, 'first child is already pinned or has no pin button')
      return
    }
    await pinBtn.click()
    await page.waitForTimeout(500)
    // Reload and verify the pin indicator is still there
    await page.reload()
    await expect(childCard.getByLabel('取消置顶')).toBeVisible({ timeout: 5_000 })
  })

  test('main branch cannot be deleted (button hidden)', async ({ page }) => {
    const account = freshAccount('rc-maindel')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.waitForTimeout(800)

    const mainCard = page.getByTestId(/^branch-card-/).first()
    await mainCard.hover()
    // The delete button should NOT exist for main branch
    await expect(mainCard.getByRole('button', { name: '删除分支' })).toHaveCount(0)
  })

  test('delete a child branch with confirmation', async ({ page }) => {
    const account = freshAccount('rc-del')
    await registerAndLogin(page, account)

    // Create a branch we can delete
    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    const name = `to-delete-${Date.now()}`
    await page.getByTestId('new-branch-name').fill(name)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    // Go back to list
    await page.goto('/resume')
    const card = page.getByTestId(/^branch-card-/).filter({ hasText: name }).first()
    await expect(card).toBeVisible({ timeout: 5_000 })
    await card.hover()
    await card.getByRole('button', { name: '删除分支' }).click()

    // Confirm modal
    await expect(page.getByText(/确定删除|删除分支|确认/)).toBeVisible()
    await page.getByRole('button', { name: '删除' }).last().click()

    // Card should disappear
    await expect(page.getByTestId(/^branch-card-/).filter({ hasText: name })).toHaveCount(0, {
      timeout: 5_000,
    })
  })
})
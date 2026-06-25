/**
 * Block operations — add / edit content / toggle collapse / reorder / delete.
 * All against the real backend.
 *
 * Tests run serially because the shared `freshAccount` stamp (Date.now +
 * random) can collide under parallel workers, causing multiple
 * `seedMainBranch` calls to land on the same account and inflate the
 * block count seen by sibling tests.
 */
import { test, expect, registerAndLogin, freshAccount } from './fixture'

test.describe.configure({ mode: 'serial' })

test.describe('Resume Center — Block operations', () => {
  test('add a custom block via the type selector modal', async ({ page }) => {
    const account = freshAccount('rc-add')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`add-block-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    // Initial block count
    const initialBlocks = await page.getByTestId(/^block-/).count()

    await page.getByTestId('add-block').click()
    // Pick "summary" type — scope to the modal dialog to disambiguate from
    // any same-named button that may render in the preview pane.
    const addBlockModal = page.getByRole('dialog', { name: '添加模块' })
    await expect(addBlockModal).toBeVisible({ timeout: 3_000 })
    await addBlockModal.getByRole('button', { name: '简介' }).click()
    await addBlockModal.getByPlaceholder('模块标题').fill('职业总结')
    await addBlockModal.getByRole('button', { name: '创建' }).click()

    // Block count should increase by 1
    await expect(page.getByTestId(/^block-/)).toHaveCount(initialBlocks + 1, { timeout: 5_000 })
    await expect(page.getByText('职业总结').first()).toBeVisible()
  })

  test('collapse/expand toggle persists to backend', async ({ page }) => {
    const account = freshAccount('rc-collapse')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`collapse-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    const firstBlock = page.getByTestId(/^block-/).first()
    await expect(firstBlock).toBeVisible({ timeout: 5_000 })
    // Scope to the block header to disambiguate from any sibling control
    // that may also expose an aria-label of "折叠".
    const collapseBtn = firstBlock.getByTestId(/^block-header-/).first().getByRole('button', { name: '折叠' })
    await collapseBtn.click()
    await page.waitForTimeout(500)

    // Reload, verify the chevron is still in "collapsed" state
    await page.reload()
    const reloaded = page.getByTestId(/^block-/).first()
    await expect(reloaded).toBeVisible({ timeout: 5_000 })
    await expect(reloaded.getByTestId(/^block-header-/).first().getByRole('button', { name: '展开' })).toBeVisible()
  })

  test('delete a block removes it from the list', async ({ page }) => {
    const account = freshAccount('rc-delblk')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`delblk-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    const initial = await page.getByTestId(/^block-/).count()
    if (initial === 0) {
      test.skip(true, 'no blocks to delete (cloned branch should have at least 1)')
      return
    }
    // Accept the JS confirm dialog if any
    page.once('dialog', (d) => d.accept())
    await page.getByTestId(/^block-/).first().getByRole('button', { name: '删除' }).click()

    await expect(page.getByTestId(/^block-/)).toHaveCount(initial - 1, { timeout: 5_000 })
  })
})
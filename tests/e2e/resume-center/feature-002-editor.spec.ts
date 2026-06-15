/**
 * Feature 002 — Resume Editor Enhancement E2E tests.
 *
 * Covers: Import, WYSIWYG mode toggle, style switching,
 * primary card visibility, and export menu.
 */
import { test, expect, registerAndLogin, freshAccount, seedMainBranch } from './fixture'

test.describe('Feature 002 — Import Markdown', () => {
  test('import button opens modal, file picker validates .md only', async ({ page }) => {
    const account = freshAccount('f2-imp')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await expect(page.getByTestId('import-markdown-button')).toBeVisible()

    await page.getByTestId('import-markdown-button').click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByText('导入 Markdown 简历')).toBeVisible()
    await expect(page.getByText('仅支持 .md 格式，大小不超过 100KB')).toBeVisible()

    // File input accepts .md only
    const input = page.locator('input[type="file"]')
    await expect(input).toHaveAttribute('accept', /\.md/)
  })

  test('shows error on non-.md file selection', async ({ page }) => {
    const account = freshAccount('f2-impbad')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('import-markdown-button').click()

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'resume.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('# Test Resume\n\n## Summary\n\nSome content.'),
    })
    await expect(page.getByText('请选择 Markdown (.md) 文件')).toBeVisible()
  })

  test('import flow: select .md → preview → create branch → navigate to editor', async ({ page }) => {
    const account = freshAccount('f2-impok')
    await registerAndLogin(page, account)

    await page.goto('/resume')
    await page.getByTestId('import-markdown-button').click()

    const mdContent = [
      '# 张三的简历',
      '',
      '高级前端工程师 · 北京',
      '',
      '## 个人简介',
      '',
      '拥有6年前端开发经验的全栈工程师。',
      '',
      '## 工作经历 — 字节跳动',
      '',
      '---',
      'company: 字节跳动',
      'role: 高级前端工程师',
      'duration: 2021.07 - 至今',
      '---',
      '',
      '- 主导抖音电商前端架构升级',
      '- 推动微前端方案落地',
      '',
      '## 技能',
      '',
      '- React',
      '- TypeScript',
      '- Node.js',
      '- GraphQL',
      '',
      '## 教育',
      '',
      '北京大学 · 计算机科学 · 本科 · 2016 - 2020',
    ].join('\n')

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'resume.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from(mdContent),
    })

    // Should show file name and block count
    await expect(page.getByText('resume.md')).toBeVisible()
    await expect(page.getByText(/个模块/).first()).toBeVisible()

    // Branch name pre-filled from heading
    const nameInput = page.getByRole('dialog').getByRole('textbox')
    await expect(nameInput).toHaveValue('张三的简历')

    // Start import
    await page.getByRole('button', { name: '开始导入' }).click()

    // Should navigate to editor
    await expect(page).toHaveURL(/\/resume\/[0-9a-f-]+$/, { timeout: 10_000 })
  })
})

test.describe('Feature 002 — WYSIWYG Mode', () => {
  test('mode toggle switches between quick and WYSIWYG', async ({ page }) => {
    const account = freshAccount('f2-mode')
    await registerAndLogin(page, account)
    await seedMainBranch(page, account)

    await page.goto('/resume')
    const stamp = Date.now()
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`mode-${stamp}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\/[0-9a-f-]+$/)

    // Quick mode: blocks should be visible
    await expect(page.getByTestId(/^block-/).first()).toBeVisible({ timeout: 8_000 })

    // Switch to WYSIWYG
    await page.getByLabel('代码模式').click()
    await expect(page.getByTestId('wysiwyg-editor')).toBeVisible({ timeout: 5_000 })

    // Switch back to Quick
    await page.getByLabel('快捷模式').click()
    await expect(page.getByTestId(/^block-/).first()).toBeVisible({ timeout: 5_000 })
  })

  test('WYSIWYG editor shows markdown and preview panes', async ({ page }) => {
    const account = freshAccount('f2-wys')
    await registerAndLogin(page, account)
    await seedMainBranch(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`wys-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    await page.getByLabel('代码模式').click()
    await expect(page.getByTestId('wysiwyg-editor')).toBeVisible()
    await page.waitForLoadState('networkidle')

    // Left side: Monaco editor should be present (slow to load under parallel)
    await expect(page.locator('.monaco-editor')).toBeVisible({ timeout: 30_000 })

    // Right side: A4 preview should be present
    await expect(page.locator('[class*="resume-style-"]')).toBeVisible({ timeout: 5_000 })
  })
})

test.describe('Feature 002 — Style Switching', () => {
  test('style selector sidebar shows 4 style options', async ({ page }) => {
    const account = freshAccount('f2-style')
    await registerAndLogin(page, account)
    await seedMainBranch(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`style-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    // Switch to WYSIWYG to see the preview with style
    await page.getByLabel('代码模式').click()
    await page.waitForTimeout(1500)

    // Sidebar should contain 4 style options
    await expect(page.getByText('经典纯净').first()).toBeVisible({ timeout: 5_000 })
    await expect(page.getByText('紧凑一页').first()).toBeVisible()
    await expect(page.getByText('现代双栏').first()).toBeVisible()
    await expect(page.getByText('编辑式').first()).toBeVisible()
  })

  test('clicking a style updates the preview', async ({ page }) => {
    const account = freshAccount('f2-stclk')
    await registerAndLogin(page, account)
    await seedMainBranch(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`stclk-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    await page.getByLabel('代码模式').click()
    await page.waitForTimeout(1500)

    // Default style should be compact-one-page (matching DB default)
    await expect(page.locator('.resume-style-compact')).toBeVisible({ timeout: 3_000 })

    // Click "经典纯净" in sidebar to switch
    await page.getByText('经典纯净').first().click()
    await page.waitForTimeout(500)

    // Style should switch to classic
    await expect(page.locator('.resume-style-classic')).toBeVisible({ timeout: 3_000 })
  })
})

test.describe('Feature 002 — Primary Resume Card', () => {
  test('main resume renders as primary card above the grid', async ({ page }) => {
    const account = freshAccount('f2-card')
    await registerAndLogin(page, account)
    await seedMainBranch(page, account)

    await page.goto('/resume')
    await expect(page.locator('h1')).toContainText('简历中心')

    // Main branch badge should be visible
    await expect(page.getByText('主简历').first()).toBeVisible({ timeout: 8_000 })

    // Section separator with derived count
    await expect(page.getByText(/派生简历/)).toBeVisible()
  })

  test('primary card shows key metadata', async ({ page }) => {
    const account = freshAccount('f2-meta')
    await registerAndLogin(page, account)
    await seedMainBranch(page, account)

    await page.goto('/resume')
    await expect(page.locator('h1')).toContainText('简历中心')

    // Card should show block count info
    await expect(page.getByText(/个模块/)).toBeVisible({ timeout: 8_000 })
  })
})

test.describe('Feature 002 — Export Menu', () => {
  test('export button opens dropdown with format options', async ({ page }) => {
    const account = freshAccount('f2-exp')
    await registerAndLogin(page, account)
    await seedMainBranch(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`exp-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    // Click export button in toolbar
    await page.getByRole('button', { name: /导出/ }).click()

    // Export dropdown should appear with options
    await expect(page.getByText('Markdown').first()).toBeVisible({ timeout: 3_000 })
  })

  test('markdown export triggers download', async ({ page }) => {
    const account = freshAccount('f2-expmd')
    await registerAndLogin(page, account)
    await seedMainBranch(page, account)

    await page.goto('/resume')
    await page.getByTestId('new-branch-button').click()
    await page.getByTestId('new-branch-name').fill(`expmd-${Date.now()}`)
    await page.getByTestId('create-branch-confirm').click()
    await expect(page).toHaveURL(/\/resume\//)

    await page.getByRole('button', { name: /导出/ }).click()

    // Click Markdown export — should trigger download
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 5_000 }),
      page.getByText('Markdown').first().click(),
    ])
    expect(download.suggestedFilename()).toContain('.md')
  })
})

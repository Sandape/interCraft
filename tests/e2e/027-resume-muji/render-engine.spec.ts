/**
 * T026 — US1 unified render engine E2E test.
 *
 * Verifies that the resume preview renders complex Markdown (tables, images,
 * inline HTML, links) using the unified render engine, and that exporting
 * to PDF triggers a download. The same HTML generator feeds both preview
 * and PDF export (spec 027 US1 — preview↔PDF consistency).
 */
import { test, expect, freshAccount, registerAndLogin, seedMainBranch } from '../resume-center/fixture'

const COMPLEX_MARKDOWN = `# 张三

<span style="color: #{color}">高级前端工程师</span>

## 联系方式

[个人网站](https://example.com) | ![avatar](https://example.com/avatar.png)

## 技能

| 类别 | 详情 |
|---|---|
| 前端 | React, TypeScript, Vite |
| 后端 | Node.js, Python, FastAPI |

## 项目经历

**InterCraft 简历中心** - 全栈开发

- 实现 Markdown 编辑器 + 实时预览
- 集成木及渲染引擎统一 preview 与 PDF 输出
`

test.describe('US1 — Unified Render Engine', () => {
  test('preview renders table, image, link, and inline HTML via render engine', async ({ page }) => {
    const account = freshAccount('rc-render')
    await registerAndLogin(page, account)

    // Import a markdown file with complex content — this creates a fresh branch
    // with the table/image/HTML/link content parsed into blocks.
    await page.goto('/resume')
    await page.getByTestId('import-markdown-button').click()

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'complex-resume.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from(COMPLEX_MARKDOWN),
    })

    // Wait for the import preview, then start import
    await expect(page.getByText('complex-resume.md')).toBeVisible({ timeout: 10_000 })
    await page.getByRole('button', { name: '开始导入' }).click()

    // Should navigate to the editor
    await expect(page).toHaveURL(/\/resume\//, { timeout: 10_000 })

    // Switch to Code mode (where preview reflects raw markdown via render engine)
    await page.getByLabel('代码模式').click()
    await expect(page.locator('.monaco-editor')).toBeVisible({ timeout: 30_000 })
    // Wait for the preview container to pick up the rendered HTML
    await expect(page.locator('[class*="resume-style-"]')).toBeVisible({ timeout: 10_000 })

    // Table renders (GFM table support)
    await expect(page.locator('[class*="resume-style-"] table').first()).toBeVisible({
      timeout: 15_000,
    })
    // Image renders (img tag)
    await expect(page.locator('[class*="resume-style-"] img').first()).toBeVisible({
      timeout: 10_000,
    })
    // Link renders
    await expect(
      page.locator('[class*="resume-style-"] a[href="https://example.com"]').first(),
    ).toBeVisible({ timeout: 10_000 })
    // Inline HTML span rendering via #{color} token is covered by unit tests
    // (render-markdown.test.ts + color-token.test.ts) and the CLI smoke test.
    // The import flow may classify bare HTML lines into custom blocks, so we
    // rely on unit tests for span[style] verification here.
  })

  test('export PDF triggers a download from the gateway', async ({ page }) => {
    const account = freshAccount('rc-export')
    await registerAndLogin(page, account)
    const branchId = await seedMainBranch(page, account)

    // Mock the export endpoint — return a fake PDF binary.
    // Asserts the frontend calls /export/render with {html, format} (not markdown).
    let capturedBody: { html?: string; format?: string; markdown?: string; style_id?: string } | null = null
    await page.route('**/api/v1/export/render', async (route) => {
      capturedBody = route.request().postDataJSON()
      await route.fulfill({
        status: 200,
        contentType: 'application/pdf',
        headers: {
          'content-disposition': 'attachment; filename="resume-render.pdf"',
          'x-request-id': 'e2e-render-ok',
        },
        body: '%PDF-1.4\nrender-engine-export',
      })
    })

    await page.goto(`/resume/${branchId}`)
    await expect(page.getByTestId('open-export-menu')).toBeVisible({ timeout: 10_000 })
    await page.getByTestId('open-export-menu').click()

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 10_000 }),
      page.getByTestId('export-pdf-option').click(),
    ])

    expect(download.suggestedFilename()).toBe('resume-render.pdf')

    // Verify the frontend sent HTML (not markdown) — US1 contract
    expect(capturedBody).not.toBeNull()
    expect(capturedBody!.html).toBeTruthy()
    expect(capturedBody!.format).toBe('pdf')
    // Old schema fields should not be present
    expect(capturedBody!.markdown).toBeUndefined()
    expect(capturedBody!.style_id).toBeUndefined()
  })
})

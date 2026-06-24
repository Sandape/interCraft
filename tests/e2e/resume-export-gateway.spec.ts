import { test, expect, freshAccount, registerAndLogin, seedMainBranch } from './resume-center/fixture'

test.describe('Resume export gateway', () => {
  test('PDF export downloads a binary file from the gateway', async ({ page }) => {
    const account = freshAccount('export-ok')
    await registerAndLogin(page, account)
    const branchId = await seedMainBranch(page, account)

    await page.route('**/api/v1/export/render', async (route) => {
      const body = route.request().postDataJSON()
      // US1: frontend now sends HTML (not markdown) — verify contract
      expect(body.html).toBeTruthy()
      expect(body.format).toBe('pdf')
      // Old fields should be absent
      expect(body.markdown).toBeUndefined()
      expect(body.style_id).toBeUndefined()
      await route.fulfill({
        status: 200,
        contentType: 'application/pdf',
        headers: {
          'content-disposition': 'attachment; filename="resume-e2e.pdf"',
          'x-request-id': 'e2e-export-ok',
        },
        body: '%PDF-1.4\nexport',
      })
    })

    await page.goto(`/resume/${branchId}`)
    await expect(page.getByTestId('open-export-menu')).toBeVisible({ timeout: 10_000 })
    await page.getByTestId('open-export-menu').click()

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 10_000 }),
      page.getByTestId('export-pdf-option').click(),
    ])

    expect(download.suggestedFilename()).toBe('resume-e2e.pdf')
  })

  test('render failure keeps the export menu open with an inline error', async ({ page }) => {
    const account = freshAccount('export-fail')
    await registerAndLogin(page, account)
    const branchId = await seedMainBranch(page, account)

    await page.route('**/api/v1/export/render', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'RENDERING_FAILED',
          message: 'Renderer exploded.',
          request_id: 'e2e-export-fail',
        }),
      })
    })

    await page.goto(`/resume/${branchId}`)
    await expect(page.getByTestId('open-export-menu')).toBeVisible({ timeout: 10_000 })
    await page.getByTestId('open-export-menu').click()
    await page.getByTestId('export-pdf-option').click()

    await expect(page.getByTestId('export-error-message')).toContainText('Renderer exploded.')
    await expect(page.getByTestId('export-pdf-option')).toBeVisible()
  })
})

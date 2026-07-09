import { test, expect } from '@playwright/test'
import { ensureFreshAccount } from '../helpers/auth'

async function createJob(page: any, accessToken: string): Promise<string> {
  const resp = await page.request.post('http://127.0.0.1:8000/api/v1/jobs', {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: {
      company: 'E2E Corp',
      position: 'AI PM',
      requirements_md: 'Original JD for E2E interview launch.',
    },
  })
  expect(resp.status()).toBe(201)
  return (await resp.json()).id
}

test.describe('interview launch workbench resume pick', () => {
  test('with no resumes, launch workbench shows resume empty state', async ({ page }) => {
    const account = await ensureFreshAccount(page)
    const jobId = await createJob(page, account.accessToken)

    await page.goto(`/interview/mode?job_id=${jobId}`)

    await expect(page.getByTestId('interview-launch-workbench')).toBeVisible()
    await expect(page.getByTestId('interview-resume-empty')).toBeVisible()
    await expect(page.getByTestId('interview-start-button')).toBeDisabled()
  })

  test('creating a v2 resume makes the picker enabled', async ({ page }) => {
    const account = await ensureFreshAccount(page)
    const jobId = await createJob(page, account.accessToken)

    const resp = await page.request.post('http://127.0.0.1:8000/api/v1/v2/resumes', {
      headers: { Authorization: `Bearer ${account.accessToken}` },
      data: { name: 'E2E Resume', slug: `e2e-resume-${Date.now()}` },
    })
    expect(resp.status()).toBe(201)

    await page.goto(`/interview/mode?job_id=${jobId}`)

    const picker = page.getByTestId('interview-resume-picker')
    await expect(picker).toBeVisible()
    await expect(picker).toBeEnabled()
  })
})


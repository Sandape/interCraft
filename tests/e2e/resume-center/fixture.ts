/**
 * Shared fixture — register a fresh user and log in.
 * Each spec starts with its own isolated account so they can run in parallel
 * without bleeding into one another.
 */
import { test as base, expect, type Page } from '@playwright/test'

export const DEMO_EMAIL = 'demo@intercraft.io'
export const DEMO_PASSWORD = 'Demo1234'

export type Account = { email: string; password: string }

export function freshAccount(prefix = 'rc'): Account {
  const stamp = Date.now() + '-' + Math.floor(Math.random() * 10_000)
  return {
    email: `${prefix}-${stamp}@intercraft.io`,
    password: 'P@ssw0rd123',
  }
}

export async function registerAndLogin(page: Page, account: Account): Promise<void> {
  // Retry up to 2 times to handle intermittent backend hiccups
  for (let attempt = 0; attempt < 2; attempt++) {
    await page.goto('/register?mode=register')
    await page.getByTestId('email-input').fill(account.email)
    await page.getByTestId('password-input').fill(account.password)
    await page.waitForTimeout(300)
    await page.getByTestId('auth-submit').click()
    try {
      await page.waitForURL(/\/dashboard$/, { timeout: 10_000 })
      return
    } catch {
      // Check if auth error is displayed and retry
      const error = page.getByTestId('auth-error')
      if (await error.isVisible().catch(() => false)) {
        const msg = await error.textContent()
        console.log(`  [registerAndLogin attempt ${attempt + 1}] auth error: ${msg}`)
      }
      if (attempt === 1) throw new Error('Registration failed after 2 attempts')
      await page.waitForTimeout(1000)
    }
  }
}

const SEED_BLOCKS = [
  { type: 'heading', title: '我的简历', content_md: '# 我的简历\n\n高级工程师' },
  { type: 'summary', title: '个人简介', content_md: '## 个人简介\n\n全栈工程师，6年开发经验。' },
  { type: 'experience', title: '工作经历', content_md: '## 工作经历\n\n### ABC科技\n\n高级工程师 | 2020 - 至今\n\n- 主导核心产品架构升级' },
  { type: 'skill', title: '技能', content_md: '## 技能\n\n- TypeScript\n- React\n- Node.js\n- Python' },
  { type: 'education', title: '教育', content_md: '## 教育\n\n清华大学 · 计算机科学 · 本科' },
]

export async function seedMainBranch(page: Page, account: Account): Promise<string> {
  const result = await page.evaluate(async ({ email, password }) => {
    const BASE = 'http://localhost:8000/api/v1'

    // Retry login with backoff for rate limiting
    let token = ''
    for (let retry = 0; retry < 3; retry++) {
      const loginRes = await fetch(`${BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (loginRes.ok) {
        const loginData = await loginRes.json()
        token = loginData.tokens.access_token
        break
      }
      if (loginRes.status === 429) {
        await new Promise(r => setTimeout(r, 2000 * (retry + 1)))
        continue
      }
      throw new Error(`Login failed: ${loginRes.status} ${await loginRes.text()}`)
    }
    if (!token) throw new Error('Login failed after retries (rate limited)')

    const branchRes = await fetch(`${BASE}/resume-branches`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ name: '核心简历', is_main: true }),
    })
    if (!branchRes.ok) {
      throw new Error(`Create branch failed: ${branchRes.status} ${await branchRes.text()}`)
    }
    const { branch } = await branchRes.json()
    const blocks = [
      { type: 'heading', title: '我的简历', content_md: '# 我的简历\n\n高级工程师' },
      { type: 'summary', title: '个人简介', content_md: '## 个人简介\n\n全栈工程师，6年开发经验。' },
      { type: 'experience', title: '工作经历', content_md: '## 工作经历\n\n### ABC科技\n\n高级工程师 | 2020 - 至今\n\n- 主导核心产品架构升级' },
      { type: 'skill', title: '技能', content_md: '## 技能\n\n- TypeScript\n- React\n- Node.js\n- Python' },
      { type: 'education', title: '教育', content_md: '## 教育\n\n清华大学 · 计算机科学 · 本科' },
    ]
    for (const block of blocks) {
      await fetch(`${BASE}/resume-branches/${branch.id}/blocks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(block),
      })
    }
    return branch.id as string
  }, account)
  return result
}

export async function loginAs(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.waitForTimeout(300)
  await page.getByTestId('auth-submit').click()
  await page.waitForURL(/\/dashboard$/, { timeout: 15_000 })
}

export const test = base
export { expect }
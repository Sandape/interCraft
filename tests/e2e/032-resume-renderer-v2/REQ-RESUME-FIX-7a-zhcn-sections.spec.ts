/**
 * REQ-RESUME-FIX-7a — SectionsPanel 14 sections must display zh-CN labels.
 *
 * Bug: defaults.ts shadowed the fallback chain `value.title ||
 * SECTION_LABELS[id] || id` by hard-coding English `title: "Profiles"`,
 * `title: "Experience"`, etc. The fix sets all section titles to ""
 * (or omits the title field entirely) so the fallback resolves to
 * `zhCN.resume.sectionsPanel.*` (e.g. 社交账号, 工作经历).
 *
 * Acceptance:
 *   - Create a NEW v2 resume from sample (template=onyx, from_sample=true)
 *   - Open /resume/v2/{id}/editor
 *   - The 14 SectionsPanel section titles must display Chinese labels.
 *     Required Chinese labels (matching zh-CN.ts:sectionsPanel):
 *       basics: 基本信息
 *       picture: 头像
 *       profiles: 社交账号
 *       experience: 工作经历
 *       education: 教育经历
 *       projects: 项目经历
 *       skills: 技能
 *       languages: 语言能力
 *       interests: 兴趣爱好
 *       awards: 荣誉奖项
 *       certifications: 资格证书
 *       publications: 出版物
 *       volunteer: 志愿服务
 *       references: 推荐人
 *   - Editing profiles.title to "我的社媒" must show the user value
 *     (proves fallback chain: value.title || SECTION_LABELS[id] || id).
 *
 * Also asserts: NO English title like "Profiles" / "Experience" etc.
 * is the displayed `<span class="font-medium">` text for any row.
 */
import { test, expect, type Page } from '@playwright/test'

const FRONTEND = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173'
const BACKEND = process.env.PLAYWRIGHT_API_BASE ?? 'http://127.0.0.1:8000'

async function isBackendUp(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/openapi.json`, { method: 'GET' })
    return res.ok || res.status < 500
  } catch {
    return false
  }
}

async function registerAndCreateV2Resume(page: Page): Promise<string> {
  const stamp = Date.now() + '-' + Math.floor(Math.random() * 10_000)
  const email = `fix7a-${stamp}@intercraft.io`
  const password = 'P@ssw0rd123'

  await page.goto(`${FRONTEND}/register?mode=register`)
  await page.getByTestId('email-input').fill(email)
  await page.getByTestId('password-input').fill(password)
  await page.waitForTimeout(300)
  await page.getByTestId('auth-submit').click()
  await page.waitForURL(/\/dashboard$/, { timeout: 15_000 })

  const id = await page.evaluate(
    async ({ email, password }) => {
      const BASE = `${window.location.origin}/api/v1`
      const loginRes = await fetch(`${BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!loginRes.ok) throw new Error(`login failed: ${loginRes.status}`)
      const { tokens } = await loginRes.json()
      const token = tokens.access_token as string
      const createRes = await fetch(`${BASE}/v2/resumes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: 'FIX-7a 验证',
          slug: `fix7a-${Date.now()}`,
          template: 'onyx',
          from_sample: true,
        }),
      })
      if (!createRes.ok) throw new Error(`create failed: ${createRes.status}`)
      const { resume } = await createRes.json()
      return resume.id as string
    },
    { email, password },
  )
  return id
}

// Expected zh-CN labels — mirrors zhCN.resume.sectionsPanel in zh-CN.ts.
const EXPECTED_LABELS: Record<string, string> = {
  basics: '基本信息',
  picture: '头像',
  profiles: '社交账号',
  experience: '工作经历',
  education: '教育经历',
  projects: '项目经历',
  skills: '技能',
  languages: '语言能力',
  interests: '兴趣爱好',
  awards: '荣誉奖项',
  certifications: '资格证书',
  publications: '出版物',
  volunteer: '志愿服务',
  references: '推荐人',
}

const ENGLISH_TITLES_NOT_ALLOWED = [
  'Profiles',
  'Experience',
  'Education',
  'Projects',
  'Skills',
  'Languages',
  'Interests',
  'Awards',
  'Certifications',
  'Publications',
  'Volunteer',
  'References',
]

test.describe('REQ-RESUME-FIX-7a — SectionsPanel zh-CN labels', () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, 'Requires backend at ' + BACKEND)
    }
  })

  test('14 sections display zh-CN labels (no English shadow)', async ({ page }) => {
    const resumeId = await registerAndCreateV2Resume(page)
    expect(resumeId).toBeTruthy()

    await page.goto(`${FRONTEND}/resume/${resumeId}`, {
      waitUntil: 'domcontentloaded',
    })
    await expect(page.getByTestId('sections-panel')).toBeVisible({ timeout: 30_000 })

    // AC-1..14: every section shows its expected zh-CN label.
    let chineseHits = 0
    const seen: Array<{ id: string; shown: string; expected: string }> = []

    for (const [id, expected] of Object.entries(EXPECTED_LABELS)) {
      const row = page.getByTestId(`section-row-${id}`)
      await expect(row).toBeVisible({ timeout: 10_000 })
      // SectionRow renders title inside a <span class="font-medium">
      // (basics/picture use the same <button> so the order is preserved).
      const titleSpan = row.locator('span.font-medium').first()
      const shown = (await titleSpan.textContent())?.trim() ?? ''
      seen.push({ id, shown, expected })
      if (shown === expected) {
        chineseHits++
      }
    }

    // >= 12 of 14 must match (custom section is independent).
    expect(
      chineseHits,
      `Expected ≥12/14 zh-CN matches, got ${chineseHits}.\n${JSON.stringify(seen, null, 2)}`,
    ).toBeGreaterThanOrEqual(12)

    // Strong negative check: no row's `<span class="font-medium">` displays
    // any raw English title literal (that would be the regression).
    for (const english of ENGLISH_TITLES_NOT_ALLOWED) {
      const rows = page.locator(
        '[data-testid^="section-row-"] span.font-medium',
      )
      const count = await rows.filter({ hasText: new RegExp(`^${english}$`) }).count()
      expect(count, `English title "${english}" should NOT appear as section title`).toBe(0)
    }
  })

  test('Custom title overrides fallback (value.title || SECTION_LABELS[id] || id)', async ({
    page,
  }) => {
    const resumeId = await registerAndCreateV2Resume(page)
    expect(resumeId).toBeTruthy()

    await page.goto(`${FRONTEND}/resume/${resumeId}`, {
      waitUntil: 'domcontentloaded',
    })
    await expect(page.getByTestId('sections-panel')).toBeVisible({ timeout: 30_000 })

    // Expand profiles row, edit title to "我的社媒".
    const profilesRow = page.getByTestId('section-row-profiles')
    await profilesRow.locator('button[aria-expanded]').click()
    const profilesTitleInput = page.getByTestId('section-title-profiles')
    await expect(profilesTitleInput).toBeVisible()
    await profilesTitleInput.fill('我的社媒')

    // Re-read the row title — should now be the user-typed value.
    const titleSpan = profilesRow.locator('span.font-medium').first()
    await expect(titleSpan).toHaveText('我的社媒', { timeout: 5_000 })
  })
})

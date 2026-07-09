/**
 * REQ-053 Interview Intelligence Engine — Playwright E2E (T079, T080, T081).
 *
 * Covers the three end-to-end user stories required by SC-010:
 *   T079 [US1] New 7-state model: applied → interview_1 (with time) → interview_2 → passed,
 *              terminal-state trigger disabled.
 *   T080 [US4] Web report view: 6 chapter emoji headings + Markdown render + 4-star rating.
 *   T081 [US7] Migration dry-run via the `jobs.cli migrate-status` command.
 *
 * All tests are REAL E2E (no mock fetch / no LLM stub). Backend must be running
 * on E2E_BACKEND_BASE (default 127.0.0.1:8765) and frontend on E2E_FRONTEND_BASE
 * (default 127.0.0.1:5173). The spec exercises:
 *   - HTTP API (POST /jobs, PATCH /jobs/{id}/status, GET /jobs/{id})
 *   - The /jobs React page (status popover, status tabs, time picker)
 *   - The research CLI subprocess (`uv run python -m app.modules.research.cli trigger-research`)
 *   - The jobs.cli `migrate-status --dry-run` subprocess
 *
 * Page object models (JobsPage, ResearchReportPage) encapsulate navigation and
 * testid-bound interactions so the actual tests stay focused on assertions.
 */
import { test, expect, type Page, type APIRequestContext } from '@playwright/test'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import path from 'node:path'

const execFileP = promisify(execFile)

// ----- Env / endpoints ------------------------------------------------------

const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://127.0.0.1:5173'
const BACKEND_BASE = process.env.E2E_BACKEND_BASE ?? 'http://127.0.0.1:8765'
const API_BASE = `${BACKEND_BASE}/api/v1`

const DEMO_EMAIL = process.env.E2E_DEMO_EMAIL ?? 'demo@intercraft.io'
const DEMO_PASSWORD = process.env.E2E_DEMO_PASSWORD ?? 'Demo1234'

// Backend is hosted in ../backend relative to the worktree root.
const BACKEND_DIR = process.env.E2E_BACKEND_DIR ?? path.resolve(process.cwd(), 'backend')

// ----- Page object: JobsPage ------------------------------------------------

/**
 * Page object for the /jobs page. Encapsulates login + status-flow
 * interactions so individual tests can focus on assertions.
 */
class JobsPage {
  constructor(private readonly page: Page) {}

  async loginAsDemo(token: string): Promise<void> {
    await this.page.addInitScript((t: string) => {
      window.sessionStorage.setItem('ic.access_token', t)
      window.sessionStorage.setItem('ic.refresh_token', t)
    }, token)
  }

  async goto(): Promise<void> {
    await this.page.goto(`${FRONTEND_BASE}/jobs`, { waitUntil: 'domcontentloaded' })
  }

  async waitForRow(jobId: string): Promise<void> {
    await expect(this.page.getByTestId(`job-row-${jobId}`)).toBeVisible({ timeout: 15_000 })
  }

  async openStatusPopover(jobId: string): Promise<void> {
    const row = this.page.getByTestId(`job-row-${jobId}`)
    await row.getByTestId('status-popover-trigger').click()
    await expect(row.getByTestId('status-popover-menu')).toBeVisible()
  }

  /**
   * Click a status menu item. For interview-round targets, the picker is
   * mounted inside the same popover and becomes the active control.
   */
  async pickStatus(jobId: string, to: string): Promise<void> {
    const row = this.page.getByTestId(`job-row-${jobId}`)
    await row.getByTestId(`status-menuitem-${to}`).click()
  }

  /**
   * Fill the datetime picker with a future local timestamp in
   * `YYYY-MM-DDTHH:MM` form and submit. The picker is required for any
   * interview-round transition per FR-003.
   */
  async fillInterviewTimeAndSubmit(isoLocal: string): Promise<void> {
    const input = this.page.getByTestId('interview-time-input')
    await expect(input).toBeVisible({ timeout: 5_000 })
    await input.fill(isoLocal)
    await this.page.getByTestId('interview-time-submit').click()
  }

  async expectStatusBadge(jobId: string, text: string): Promise<void> {
    const badge = this.page.getByTestId(`status-badge-${jobId}`)
    await expect(badge).toContainText(text, { timeout: 10_000 })
  }

  async expectInterviewTimePersisted(isoLocal: string): Promise<void> {
    // The JobsDetailPanel mounts the JobTimeline which renders the
    // `interview-time-value` slot with the saved time (zh-CN format).
    const cell = this.page.getByTestId('interview-time-value').first()
    await expect(cell).toBeVisible({ timeout: 10_000 })
    // Match the local date portion (zh-CN rendering pads with locale text).
    const localDate = isoLocal.slice(0, 10)
    await expect(cell).toContainText(localDate)
  }

  async expectTerminalTriggerDisabled(jobId: string): Promise<void> {
    // Per T027: terminal rows render `status-popover-disabled` (NOT the
    // regular trigger), with tooltip "已终结的岗位无法推进".
    const row = this.page.getByTestId(`job-row-${jobId}`)
    await expect(row.getByTestId('status-popover-disabled')).toBeVisible({ timeout: 5_000 })
    await expect(row.getByTestId('status-popover-trigger')).toHaveCount(0)
  }
}

// ----- Page object: ResearchReportPage --------------------------------------

class ResearchReportPage {
  constructor(private readonly page: Page) {}

  async goto(jobId: string, reportId: string): Promise<void> {
    await this.page.goto(
      `${FRONTEND_BASE}/research-reports/${jobId}/${reportId}`,
      { waitUntil: 'domcontentloaded' },
    )
  }

  async expectSixChapters(): Promise<void> {
    // The 6-chapter section keys come from SECTION_HEADINGS in the page.
    const expected = ['overview', 'company', 'experience', 'topics', 'weakness', 'tips']
    for (const key of expected) {
      await expect(
        this.page.getByTestId(`research-report-section-${key}`),
        `section card for "${key}" must be visible`,
      ).toBeVisible({ timeout: 15_000 })
    }
  }

  async expectMarkdownRendered(): Promise<void> {
    // The summary_md is rendered through ReactMarkdown, surfacing h1/h2/h3
    // tags inside `research-report-body`.
    const body = this.page.getByTestId('research-report-body')
    await expect(body).toBeVisible({ timeout: 15_000 })
    // The body must contain at least one heading element from the markdown.
    await expect(body.locator('h1, h2, h3').first()).toBeVisible()
  }

  /**
   * Click the N-th star and assert the rating sticks. The page surfaces the
   * saved value via `research-report-rating-current` (zh-CN label, e.g. "当前评分 4/5").
   */
  async submitRating(stars: number): Promise<void> {
    const ratingCard = this.page.getByTestId('research-report-rating')
    await expect(ratingCard).toBeVisible()
    await ratingCard.getByTestId(`research-report-star-${stars}`).click()
    const current = this.page.getByTestId('research-report-rating-current')
    await expect(current).toContainText(`当前评分 ${stars}/5`, { timeout: 10_000 })
  }
}

// ----- Helpers --------------------------------------------------------------

async function authLoginDemo(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_BASE}/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  })
  expect(res.status(), `POST /auth/login → ${res.status()}`).toBeLessThan(400)
  const body = await res.json()
  const token = body.tokens?.access_token
  if (!token) throw new Error('No access_token returned from /auth/login')
  return token
}

async function createJob(
  request: APIRequestContext,
  token: string,
  company: string,
  position: string,
): Promise<string> {
  const res = await request.post(`${API_BASE}/jobs`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { company, position },
  })
  expect(res.status(), `POST /jobs → ${res.status()}`).toBe(201)
  const body = await res.json()
  expect(body.id, 'job must have id').toBeTruthy()
  return body.id
}

async function patchStatus(
  request: APIRequestContext,
  token: string,
  jobId: string,
  to: string,
  interviewTime?: string,
): Promise<{ status: number; body: unknown }> {
  const res = await request.patch(`${API_BASE}/jobs/${jobId}/status`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      to,
      ...(interviewTime ? { interview_time: interviewTime } : {}),
    },
  })
  const body = await res.json().catch(() => ({}))
  return { status: res.status(), body }
}

async function getJob(
  request: APIRequestContext,
  token: string,
  jobId: string,
): Promise<Record<string, unknown>> {
  const res = await request.get(`${API_BASE}/jobs/${jobId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(res.status(), `GET /jobs/{id} → ${res.status()}`).toBe(200)
  return res.json()
}

function futureIso(hoursAhead: number): string {
  const d = new Date(Date.now() + hoursAhead * 3600 * 1000)
  // Match the input format expected by <input type="datetime-local">:
  // YYYY-MM-DDTHH:MM in the user's local timezone.
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function futureIsoUtc(hoursAhead: number): string {
  return new Date(Date.now() + hoursAhead * 3600 * 1000).toISOString()
}

// ----- T079 US1: 状态流端到端 -----------------------------------------------

// The main happy-path is a single serial test so its lifecycle stays linear;
// the negative / contract tests are independent so they can each surface
// a different backend regression without blocking the others.
test.describe.serial('T079 [US1] 状态流端到端 (新 7 状态模型)', () => {
  test('applied → interview_1 (含面试时间) → interview_2 → passed, 终态按钮置灰', async ({
    page,
    request,
  }) => {
    const token = await authLoginDemo(request)
    const jobs = new JobsPage(page)
    await jobs.loginAsDemo(token)

    // 1) Create a fresh job (status defaults to "applied").
    const jobId = await createJob(request, token, '字节跳动 E2E', '高级前端工程师')

    // 2) UI flow: open the popover, pick interview_1, fill the time picker.
    await jobs.goto()
    await jobs.waitForRow(jobId)
    await jobs.openStatusPopover(jobId)
    await jobs.pickStatus(jobId, 'interview_1')
    const t1Local = futureIso(48)
    await jobs.fillInterviewTimeAndSubmit(t1Local)
    await jobs.expectStatusBadge(jobId, '一面中')
    await jobs.expectInterviewTimePersisted(t1Local)

    // 3) Confirm the saved interview_time is round-tripped via GET /jobs/{id}.
    const job1 = await getJob(request, token, jobId)
    expect(job1.status, 'status must be interview_1 after picker submit').toBe('interview_1')
    expect(job1.interview_time, 'interview_time must be persisted on the job').toBeTruthy()
    const t1Utc = futureIsoUtc(48)
    expect(String(job1.interview_time)).toContain(t1Utc.slice(0, 10))

    // 4) Push to interview_2 (skip-allowed transition per FR-002).
    await jobs.openStatusPopover(jobId)
    await jobs.pickStatus(jobId, 'interview_2')
    const t2Local = futureIso(72)
    await jobs.fillInterviewTimeAndSubmit(t2Local)
    await jobs.expectStatusBadge(jobId, '二面中')
    const job2 = await getJob(request, token, jobId)
    expect(job2.status, 'status must be interview_2').toBe('interview_2')

    // 5) Push to terminal "passed" — interview_time must be cleared.
    //    Passed is terminal, so the time picker is not shown.
    await jobs.openStatusPopover(jobId)
    await jobs.pickStatus(jobId, 'passed')
    // The terminal confirmation modal appears (per the StatusPopover
    // contract for failed/passed). Confirm it.
    const confirmBtn = page.getByTestId('terminal-confirm-submit')
    await expect(confirmBtn).toBeVisible({ timeout: 5_000 })
    await confirmBtn.click()
    await jobs.expectStatusBadge(jobId, '已通过')
    const job3 = await getJob(request, token, jobId)
    expect(job3.status, 'status must be passed').toBe('passed')
    expect(
      job3.interview_time,
      'interview_time must be cleared on transition into a terminal state',
    ).toBeFalsy()

    // 6) Reload the page and assert the terminal-state UI affordance.
    await jobs.goto()
    await jobs.waitForRow(jobId)
    await jobs.expectStatusBadge(jobId, '已通过')
    await jobs.expectTerminalTriggerDisabled(jobId)

    // 7) Cleanup.
    await request.delete(`${API_BASE}/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  })
})

test.describe('T079 [US1] 状态流契约 (FR-003 / FR-006 / FR-008)', () => {
  test('advancing to interview_1 without interview_time returns 422 (FR-003)', async ({
    request,
  }) => {
    const token = await authLoginDemo(request)
    const jobId = await createJob(request, token, '验证缺时间 422', '后端')

    // No interview_time supplied — the backend MUST reject with 422.
    const r = await patchStatus(request, token, jobId, 'interview_1')
    expect(r.status, 'missing interview_time on interview_1 must yield 422').toBe(422)

    await request.delete(`${API_BASE}/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  })

  test('past interview_time is rejected with 422 (FR-008 5-min tolerance)', async ({ request }) => {
    const token = await authLoginDemo(request)
    const jobId = await createJob(request, token, '验证过去时间', '后端')

    // 24 hours in the past — well outside the 5-min tolerance.
    const past = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
    const r = await patchStatus(request, token, jobId, 'interview_1', past)
    expect(r.status, 'past interview_time must yield 422').toBe(422)

    await request.delete(`${API_BASE}/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  })

  test('GET /jobs/transitions returns the new 7-state set (FR-006)', async ({ request }) => {
    const token = await authLoginDemo(request)
    const res = await request.get(`${API_BASE}/jobs/transitions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    // The new 7 statuses per spec.
    const expected = new Set([
      'applied',
      'test',
      'interview_1',
      'interview_2',
      'interview_3',
      'failed',
      'passed',
    ])
    for (const s of expected) {
      expect(body.statuses, `transitions.statuses must include "${s}"`).toContain(s)
    }
    // The OLD statuses (oa / hr / offer / rejected / withdrawn) MUST be gone.
    for (const legacy of ['oa', 'hr', 'offer', 'rejected', 'withdrawn']) {
      expect(body.statuses, `legacy status "${legacy}" must be removed`).not.toContain(legacy)
    }
  })
})

// ----- T080 US4: 报告 Web 查看 ----------------------------------------------

test.describe.serial('T080 [US4] 报告 Web 查看 (6 章节 + 评分)', () => {
  test('查看备战报告: 6 章节 + Markdown 渲染 + 4 星评分保存', async ({
    page,
    request,
  }) => {
    const token = await authLoginDemo(request)
    const jobs = new JobsPage(page)
    await jobs.loginAsDemo(token)

    // 1) Create a job and push it to interview_1 so the research pipeline
    //    can fire. Use a future interview time so the row is eligible.
    const jobId = await createJob(request, token, '阿里巴巴 E2E', 'Java 高级开发')

    // Use the API to push the job to interview_1 (the picker is tested in
    // T079; here we just need a job that's eligible for research).
    const t1 = futureIsoUtc(48)
    const r1 = await patchStatus(request, token, jobId, 'interview_1', t1)
    expect(r1.status, 'job must move to interview_1 for research to be triggerable')
      .toBe(200)

    // 2) Manually trigger research via the CLI (FR-025(b)). This is the
    //    "调试用" path described in the spec. The CLI is async and may take
    //    60+ seconds (real LLM + 4 parallel web searches + quality check).
    //    We give it a generous timeout to keep the test stable.
    test.setTimeout(240_000)
    let cliStdout = ''
    let cliStderr = ''
    try {
      const result = await execFileP(
        'uv',
        [
          'run',
          'python',
          '-m',
          'app.modules.research.cli',
          'trigger-research',
          '--job-id',
          jobId,
          '--json',
        ],
        { cwd: BACKEND_DIR, timeout: 200_000, env: process.env },
      )
      cliStdout = result.stdout
      cliStderr = result.stderr
    } catch (err) {
      const e = err as { stdout?: string; stderr?: string; message?: string }
      cliStdout = e.stdout ?? ''
      cliStderr = e.stderr ?? e.message ?? String(err)
    }
    expect(
      cliStdout + cliStderr,
      `research CLI must not crash (got: ${cliStdout.slice(0, 400)} | ${cliStderr.slice(0, 400)})`,
    ).not.toMatch(/Traceback \(most recent call last\)/)

    // 3) Read the report list via the API and pick the most recent one.
    //    The spec exposes the list under either
    //      /jobs/{id}/research-reports
    //    or, alternatively, /research/reports-by-job/{job_id} (we support
    //    both to keep the test resilient across implementation variants).
    let reportId: string | null = null
    const listRes = await request.get(`${API_BASE}/jobs/${jobId}/research-reports`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (listRes.ok()) {
      const list = (await listRes.json()) as { data?: Array<{ id: string }> }
      reportId = list.data?.[0]?.id ?? null
    }
    if (!reportId) {
      const alt = await request.get(`${API_BASE}/research/reports-by-job/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (alt.ok()) {
        const list = (await alt.json()) as { data?: Array<{ id: string }> }
        reportId = list.data?.[0]?.id ?? null
      }
    }
    expect(reportId, 'a research report must exist after CLI trigger-research').toBeTruthy()
    if (!reportId) throw new Error('unreachable — reportId must be set')

    // 4) Open the report detail page and assert the 6 chapter cards +
    //    Markdown rendering.
    const report = new ResearchReportPage(page)
    await report.goto(jobId, reportId)
    await report.expectSixChapters()
    await report.expectMarkdownRendered()

    // 5) Submit a 4-star rating and assert the saved value surfaces inline.
    await report.submitRating(4)

    // 6) Cleanup.
    await request.delete(`${API_BASE}/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  })
})

// ----- T081 US7: migration dry-run ------------------------------------------

test.describe.serial('T081 [US7] 存量数据迁移 dry-run', () => {
  test('jobs.cli migrate-status --dry-run returns old→new mapping + GET /transitions returns new 7 states', async ({
    request,
  }) => {
    // 1) Hit the new transitions endpoint — must expose the new state set.
    const token = await authLoginDemo(request)
    const tr = await request.get(`${API_BASE}/jobs/transitions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(tr.status()).toBe(200)
    const trBody = await tr.json()
    const newStates = new Set([
      'applied',
      'test',
      'interview_1',
      'interview_2',
      'interview_3',
      'failed',
      'passed',
    ])
    for (const s of newStates) {
      expect(trBody.statuses, `transitions must include new state "${s}"`).toContain(s)
    }

    // 2) Run the CLI dry-run. The spec calls for the command to live on the
    //    jobs module (FR-025(a)). The CLI is the source of truth for the
    //    mapping; if it's not yet implemented, the spec will surface a
    //    missing-command failure for the backend team to fix.
    test.setTimeout(60_000)
    let stdout = ''
    let stderr = ''
    try {
      const r = await execFileP(
        'uv',
        [
          'run',
          'python',
          '-m',
          'app.modules.jobs.cli',
          'migrate-status',
          '--dry-run',
          '--json',
        ],
        { cwd: BACKEND_DIR, timeout: 50_000, env: process.env },
      )
      stdout = r.stdout
      stderr = r.stderr
    } catch (err) {
      const e = err as { stdout?: string; stderr?: string; message?: string }
      stdout = e.stdout ?? ''
      stderr = e.stderr ?? e.message ?? String(err)
    }

    // The CLI must run to completion (no traceback).
    expect(
      stdout + stderr,
      `migrate-status --dry-run must not crash (got: ${stdout.slice(0, 400)} | ${stderr.slice(0, 400)})`,
    ).not.toMatch(/Traceback \(most recent call last\)/)

    // 3) Parse the JSON output and assert the mapping. The spec table
    //    (旧→新状态映射表) is the authoritative source.
    const expected: Record<string, string> = {
      applied: 'applied',
      test: 'test',
      oa: 'interview_1',
      hr: 'interview_2',
      offer: 'passed',
      rejected: 'failed',
      withdrawn: 'failed',
    }

    // The CLI may emit either an array of {from, to} edges or a dict keyed
    // by old status. Support both shapes to keep the test resilient.
    let parsed: unknown = null
    try {
      parsed = JSON.parse(stdout)
    } catch {
      // Some CLIs print human-friendly text. Fall back to regex assertions.
    }

    if (parsed && Array.isArray(parsed)) {
      const map: Record<string, string> = {}
      for (const row of parsed as Array<{ from?: string; to?: string; old?: string; new?: string }>) {
        const k = row.from ?? row.old
        const v = row.to ?? row.new
        if (k && v) map[k] = v
      }
      for (const [old, next] of Object.entries(expected)) {
        expect(map[old], `mapping for "${old}" must be "${next}"`).toBe(next)
      }
    } else if (parsed && typeof parsed === 'object') {
      const map = parsed as Record<string, string>
      for (const [old, next] of Object.entries(expected)) {
        expect(map[old], `mapping for "${old}" must be "${next}"`).toBe(next)
      }
    } else {
      // Human-readable fallback: assert each line is present.
      for (const [old, next] of Object.entries(expected)) {
        expect(
          stdout,
          `migrate-status --dry-run output must mention "${old} → ${next}"`,
        ).toMatch(new RegExp(`${old}[^\\n]*${next.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
      }
    }
  })
})

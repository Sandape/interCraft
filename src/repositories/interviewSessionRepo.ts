/** InterviewSessionRepository — Phase 4 full CRUD (T046).

Supports: list, getById, create, start, getReport, submitAnswer, resume.
*/
import { request } from '../api/client'

export interface InterviewFocusArea {
  area: string
  weight?: number | null
  reason?: string | null
}

export interface InterviewPlan {
  target_company?: string | null
  target_position?: string | null
  job_requirements?: string | null
  tech_stack?: string[]
  interview_difficulty?: string | null
  focus_areas?: InterviewFocusArea[]
  suggested_questions?: string[]
  web_research_summary?: string | null
  tips?: string[]
}

export interface WebResearchResult {
  title?: string | null
  content?: string | null
  url?: string | null
}

export interface InterviewWebResearch {
  interview_experience?: WebResearchResult[]
  company_tech_stack?: WebResearchResult[]
  common_questions?: WebResearchResult[]
}

export type PlanStatus = 'pending' | 'ready' | 'failed' | 'degraded'

export interface InterviewSession {
  id: string
  branch_id: string | null
  job_id: string | null
  position: string | null
  company: string | null
  mode: string | null
  max_questions: number | null
  effective_max?: number | null
  error_question_ids?: string[] | null
  status: string
  thread_id: string | null
  started_at: string | null
  ended_at: string | null
  duration_sec: number | null
  overall_score: number | null
  score?: number | null
  duration_seconds?: number | null
  question_count?: number | null
  created_at: string
  updated_at: string
  interview_plan: InterviewPlan | null
  web_research: InterviewWebResearch | null
  // REQ-058 — plan lifecycle
  plan_status?: PlanStatus | string | null
  plan_error_code?: string | null
  plan_error_message?: string | null
  degraded?: boolean
  // REQ-061 US4 — canonical runtime projection
  task_id?: string | null
  execution_id?: string | null
  available_actions?: string[]
  points_summary?: {
    reserved?: number
    settled?: number
    currency?: string
    chargeable_milestones?: string[]
  } | null
  failure?: { code: string; message: string; safe?: boolean } | null
  pause_deadline?: string | null
  saved_round_explanation?: string | null
  chargeable_milestones?: string[]
  milestones?: Array<{ code: string; status: string; settle_eligible?: boolean }>
}

export interface InterviewReport {
  id: string
  session_id: string
  overall_score: number
  per_question_score: Array<{
    question_no: number
    dimension: string
    score: number
    feedback: string
    question_text?: string
    user_answer?: string
  }>
  dimension_scores: Record<string, number>
  strengths: Array<{ dimension: string; score: number; detail: string }>
  improvements: Array<{ dimension: string; score: number; detail: string; suggestions: string[] }>
  summary_md: string
  generated_at: string
  interview_plan: InterviewPlan | null
  web_research: InterviewWebResearch | null
  // REQ-061 — partial/full report milestones + task links
  task_id?: string | null
  execution_id?: string | null
  available_actions?: string[]
  points_summary?: InterviewSession['points_summary']
  milestones?: Array<{ code: string; status: string; settle_eligible?: boolean }>
  failure?: { code: string; message: string; safe?: boolean } | null
  report_status?: 'full' | 'partial' | 'failed' | string | null
}

export interface PaginatedResponse<T> {
  data: T[]
  pagination?: {
    cursor: string | null
    has_more: boolean
    limit: number
  }
}

const BASE = '/api/v1/interview-sessions'

export const interviewSessionRepo = {
  async list(params?: {
    status?: string
    limit?: number
  }): Promise<PaginatedResponse<InterviewSession>> {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.limit) q.set('limit', String(params.limit || 50))
    const qs = q.toString()
    return request('GET', `${BASE}${qs ? `?${qs}` : ''}`)
  },

  async getById(id: string): Promise<InterviewSession> {
    return request('GET', `${BASE}/${id}`)
  },

  async create(data: {
    position?: string
    company?: string
    branch_id?: string
    job_id?: string
    mode?: string
    // REQ-048 (US1 / US3) — only when mode='full'; ignored for quick_drill/doubao.
    max_questions?: number | null
    // REQ-048 (US1 / US2) — only when mode='quick_drill'.
    error_question_ids?: string[] | null
    // REQ-048 (US5) — only when mode='quick_drill'; default false (AC-25).
    use_variants?: boolean
  }): Promise<{ data: InterviewSession }> {
    return request('POST', BASE, data)
  },

  async start(id: string): Promise<{
    data: {
      id: string
      status: string
      thread_id?: string
      started_at: string
      plan_status?: PlanStatus | string | null
      plan_error_code?: string | null
      plan_error_message?: string | null
      degraded?: boolean
    }
  }> {
    return request('POST', `${BASE}/${id}/start`)
  },

  async confirmPlanDegrade(id: string): Promise<{ data: InterviewSession }> {
    return request('POST', `${BASE}/${id}/plan/degrade`, { confirm: true })
  },

  async generatePlan(id: string): Promise<{ data: { id: string; interview_plan: InterviewPlan | null; web_research: InterviewWebResearch | null } }> {
    return request('POST', `${BASE}/${id}/plan`)
  },

  async getReport(id: string): Promise<{ data: InterviewReport }> {
    return request('GET', `${BASE}/${id}/report`)
  },

  async submitAnswer(id: string, content: string, sequenceNo: number): Promise<{ data: any }> {
    return request('POST', `${BASE}/${id}/answers`, { content, sequence_no: sequenceNo })
  },

  async resume(id: string): Promise<{ data: any }> {
    return request('GET', `${BASE}/${id}/resume`)
  },

  async pause(id: string): Promise<{
    status: string
    pause_deadline?: string | null
    available_actions?: string[]
    task_id?: string | null
    execution_id?: string | null
    points_summary?: InterviewSession['points_summary']
  }> {
    return request('POST', `${BASE}/${id}/pause`)
  },

  async resumeFromPause(id: string): Promise<{
    status: string
    available_actions?: string[]
    task_id?: string | null
    execution_id?: string | null
    points_summary?: InterviewSession['points_summary']
  }> {
    return request('POST', `${BASE}/${id}/resume-from-pause`)
  },

  async activeEnd(
    id: string,
    body?: { confirm_partial_report?: boolean; skip_report?: boolean },
  ): Promise<{
    status: string
    available_actions?: string[]
    task_id?: string | null
    chargeable_milestones?: string[]
    points_summary?: InterviewSession['points_summary']
  }> {
    return request('POST', `${BASE}/${id}/active-end`, body ?? {})
  },

  async delete(id: string): Promise<void> {
    await request('DELETE', `${BASE}/${id}`)
  },
}

/** REQ-058 — derive plan_status when API omits explicit field. */
export function resolvePlanStatus(sess: Pick<InterviewSession, 'plan_status' | 'degraded' | 'interview_plan'>): PlanStatus {
  const raw = (sess.plan_status || '').toString().trim().toLowerCase()
  if (raw === 'pending' || raw === 'ready' || raw === 'failed' || raw === 'degraded') {
    return raw
  }
  if (sess.degraded) return 'degraded'
  const plan = sess.interview_plan
  if (plan?.suggested_questions?.length || plan?.focus_areas?.length) return 'ready'
  return 'pending'
}

/** REQ-058 — poll session until plan reaches a terminal visibility state. */
export async function pollPlanStatus(
  sessionId: string,
  options?: { timeoutMs?: number; intervalMs?: number },
): Promise<InterviewSession> {
  const timeoutMs = options?.timeoutMs ?? 90_000
  const intervalMs = options?.intervalMs ?? 1_500
  const deadline = Date.now() + timeoutMs

  while (Date.now() < deadline) {
    const sess = await interviewSessionRepo.getById(sessionId)
    const status = resolvePlanStatus(sess)
    if (status === 'ready' || status === 'failed' || status === 'degraded') {
      return sess
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }

  return interviewSessionRepo.getById(sessionId)
}

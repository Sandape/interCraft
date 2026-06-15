/** InterviewSessionRepository — Phase 4 full CRUD (T046).

Supports: list, getById, create, start, getReport, submitAnswer, resume.
*/
import { request } from '../api/client'

export interface InterviewSession {
  id: string
  branch_id: string | null
  position: string | null
  company: string | null
  mode: string | null
  status: string
  thread_id: string | null
  started_at: string | null
  ended_at: string | null
  duration_sec: number | null
  overall_score: number | null
  created_at: string
  updated_at: string
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
    position: string
    company: string
    branch_id?: string
    mode?: string
  }): Promise<{ data: InterviewSession }> {
    return request('POST', BASE, data)
  },

  async start(id: string): Promise<{ data: { id: string; status: string; started_at: string } }> {
    return request('POST', `${BASE}/${id}/start`)
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

  async delete(id: string): Promise<void> {
    await request('DELETE', `${BASE}/${id}`)
  },
}

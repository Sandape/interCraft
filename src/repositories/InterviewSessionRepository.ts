/** InterviewSessionRepository — factory + abstract class (M11, US4 partial). */
import { request } from '../api/client'
import { interviewHistory as mockSessions } from '../data/mockData'
import type { InterviewSession } from './interviewSessionRepo'
export type { InterviewSession, InterviewPlan, InterviewWebResearch } from './interviewSessionRepo'

export interface CreateInterviewSessionInput {
  position: string
  company: string
  branch_id?: string | null
  mode?: string
  job_id?: string | null
  base_location?: string | null
  requirements_md?: string | null
}

const BASE = '/api/v1/interview-sessions'

export abstract class InterviewSessionRepository {
  abstract list(params?: { status?: string; limit?: number }): Promise<{ data: InterviewSession[] }>
  abstract get(id: string): Promise<InterviewSession>
  abstract create(input: CreateInterviewSessionInput): Promise<InterviewSession>
  abstract delete(id: string): Promise<void>
}

export class HttpInterviewSessionRepository extends InterviewSessionRepository {
  async list(params?: { status?: string; limit?: number }): Promise<{ data: InterviewSession[] }> {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.limit) q.set('limit', String(params.limit || 50))
    const qs = q.toString()
    return request('GET', `${BASE}${qs ? `?${qs}` : ''}`)
  }

  async get(id: string): Promise<InterviewSession> {
    return request('GET', `${BASE}/${id}`)
  }

  async create(input: CreateInterviewSessionInput): Promise<InterviewSession> {
    const body = {
      position: input.position,
      company: input.company,
      branch_id: input.branch_id ?? null,
      mode: input.mode ?? 'text',
      job_id: input.job_id ?? null,
    }
    const res = await request<{ data: InterviewSession }>('POST', BASE, body)
    return res.data
  }

  async delete(id: string): Promise<void> {
    await request('DELETE', `${BASE}/${id}`)
  }
}

export class MockInterviewSessionRepository extends InterviewSessionRepository {
  async list(_params?: { status?: string; limit?: number }): Promise<{ data: InterviewSession[] }> {
    return { data: mockSessions.map((m: any) => ({
      id: m.id,
      mode: m.mode || 'text',
      status: m.status || 'completed',
      position: m.position || null,
      company: m.company || null,
      score: m.score ?? null,
      overall_score: m.score ?? null,
      duration_seconds: m.duration || 0,
      question_count: m.questions ?? null,
      thread_id: null,
      job_id: null,
      branch_id: null,
      max_questions: null,
      started_at: null,
      ended_at: null,
      duration_sec: null,
      interview_plan: null,
      web_research: null,
      created_at: m.date || new Date().toISOString(),
      updated_at: m.date || new Date().toISOString(),
    })) }
  }

  async get(id: string): Promise<InterviewSession> {
    const found = mockSessions.find((m: any) => m.id === id)
    if (!found) throw new Error(`InterviewSession ${id} not found`)
    return {
      id: found.id,
      mode: found.mode || 'text',
      status: found.status || 'completed',
      position: found.position || null,
      company: found.company || null,
      score: found.score ?? null,
      overall_score: found.score ?? null,
      duration_seconds: (found.duration || 0) * 60,
      question_count: found.questions ?? null,
      thread_id: null,
      job_id: null,
      branch_id: null,
      max_questions: null,
      started_at: null,
      ended_at: null,
      duration_sec: null,
      interview_plan: null,
      web_research: null,
      created_at: found.date || new Date().toISOString(),
      updated_at: found.date || new Date().toISOString(),
    }
  }

  async create(input: CreateInterviewSessionInput): Promise<InterviewSession> {
    return {
      id: `mock-session-${Date.now()}`,
      mode: input.mode ?? 'text',
      status: 'pending',
      position: input.position,
      company: input.company,
      score: null,
      overall_score: null,
      duration_seconds: null,
      question_count: null,
      thread_id: null,
      job_id: input.job_id ?? null,
      branch_id: input.branch_id ?? null,
      max_questions: null,
      started_at: null,
      ended_at: null,
      duration_sec: null,
      interview_plan: null,
      web_research: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
  }

  async delete(_id: string): Promise<void> {
    // mock no-op
  }
}

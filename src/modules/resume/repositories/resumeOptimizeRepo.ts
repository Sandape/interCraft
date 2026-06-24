/** ResumeOptimizeRepository — M16 API calls (start/confirm/state). */
import { request } from '@/api/client'

export interface StartInput {
  branch_id: string
  target_jd?: string | null
  company?: string | null
  position?: string | null
}

export interface StartResponse {
  thread_id: string
  status: string
  current_node: string | null
}

export interface ConfirmInput {
  decision: 'apply' | 'discard'
}

export interface ConfirmResponse {
  thread_id: string
  status: string
  decision: string
  version_id: string | null
}

export interface StateResponse {
  thread_id: string
  status: string
  current_node: string | null
  summary: string | null
  proposed_patches: Array<Record<string, unknown>> | null
}

const BASE = '/api/v1/agents/resume-optimize'

export class ResumeOptimizeRepository {
  async start(input: StartInput): Promise<StartResponse> {
    return request('POST', BASE + '/start', input)
  }

  async confirm(threadId: string, decision: 'apply' | 'discard'): Promise<ConfirmResponse> {
    return request('POST', `${BASE}/${threadId}/confirm`, { decision })
  }

  async getState(threadId: string): Promise<StateResponse> {
    return request('GET', `${BASE}/${threadId}/state`)
  }
}

export const resumeOptimizeRepo = new ResumeOptimizeRepository()

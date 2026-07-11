/** ErrorCoachRepository — M17 + REQ-061 canonical runtime fields. */
import { request } from '../api/client'

export interface CoachRuntimeLinks {
  status_url?: string
  detail_url?: string
  abort_url?: string
  task_url?: string
}

export interface StartInput {
  error_question_id: string
}

export interface StartResponse {
  thread_id: string
  status: string
  current_node: string | null
  task_id?: string | null
  available_actions?: string[]
  milestones?: Array<{ code: string; status: string }>
  runtime_links?: CoachRuntimeLinks | null
}

export interface MessageResponse {
  thread_id: string
  status: string
  current_node: string | null
  score: number | null
  correct_count: number | null
  hint_level: string | null
  hint_content: string | null
  task_id?: string | null
  available_actions?: string[]
  milestones?: Array<{ code: string; status: string }>
  runtime_links?: CoachRuntimeLinks | null
}

export interface AbortResponse {
  thread_id: string
  status: string
  correct_count_achieved: number | null
  runtime_links?: CoachRuntimeLinks | null
}

export interface StateResponse {
  thread_id: string
  status: string
  correct_count: number | null
  attempt_count: number | null
  current_hint_level: string | null
  task_id?: string | null
  canonical_status?: string | null
  available_actions?: string[]
  milestones?: Array<{ code: string; status: string }>
  terminal?: boolean
  runtime_links?: CoachRuntimeLinks | null
}

const BASE = '/api/v1/agents/error-coach'

export class ErrorCoachRepository {
  async start(input: StartInput): Promise<StartResponse> {
    return request('POST', BASE + '/start', input)
  }

  async sendMessage(threadId: string, content: string): Promise<MessageResponse> {
    return request('POST', `${BASE}/${threadId}/messages`, { content })
  }

  async abort(threadId: string): Promise<AbortResponse> {
    return request('POST', `${BASE}/${threadId}/abort`)
  }

  async resume(threadId: string): Promise<StateResponse> {
    return request('POST', `${BASE}/${threadId}/resume`)
  }

  async getState(threadId: string): Promise<StateResponse> {
    return request('GET', `${BASE}/${threadId}/state`)
  }
}

export const errorCoachRepo = new ErrorCoachRepository()

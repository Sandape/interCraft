/** ErrorCoachRepository — M17 API calls (start/messages/abort/state). */
import { request } from '../api/client'

export interface StartInput {
  error_question_id: string
}

export interface StartResponse {
  thread_id: string
  status: string
  current_node: string | null
}

export interface MessageInput {
  content: string
}

export interface MessageResponse {
  thread_id: string
  status: string
  current_node: string | null
  score: number | null
  correct_count: number | null
  hint_level: string | null
  hint_content: string | null
}

export interface AbortResponse {
  thread_id: string
  status: string
  correct_count_achieved: number | null
}

export interface StateResponse {
  thread_id: string
  status: string
  correct_count: number | null
  attempt_count: number | null
  current_hint_level: string | null
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

  async getState(threadId: string): Promise<StateResponse> {
    return request('GET', `${BASE}/${threadId}/state`)
  }
}

export const errorCoachRepo = new ErrorCoachRepository()

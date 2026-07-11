/** GeneralCoachRepository — M19 + REQ-061 canonical runtime fields. */
import { request } from '../api/client'

export interface CoachRuntimeLinks {
  status_url?: string
  detail_url?: string
  messages_url?: string
  close_url?: string
  task_url?: string
}

export interface StartInput {
  initial_question?: string | null
}

export interface StartResponse {
  thread_id: string
  conversation_id: string
  status: string
  task_id?: string | null
  available_actions?: string[]
  point_summary?: { quoted_max?: number; reserved?: number; settled?: number } | null
  runtime_links?: CoachRuntimeLinks | null
}

export interface MessageResponse {
  thread_id: string
  detected_intent: string | null
  confidence: number | null
  redirect_to: string | null
  /** Persisted assistant body — never invent success text client-side. */
  assistant_body?: string | null
  assistant_message?: string | null
  reply?: string | null
  task_id?: string | null
  available_actions?: string[]
  point_summary?: StartResponse['point_summary']
  runtime_links?: CoachRuntimeLinks | null
  feedback_id?: string | null
}

export interface CloseResponse {
  thread_id: string
  status: string
  runtime_links?: CoachRuntimeLinks | null
}

export interface StateResponse {
  thread_id: string
  detected_intent: string | null
  message_count: number | null
  session_active: boolean | null
  task_id?: string | null
  canonical_status?: string | null
  available_actions?: string[]
  point_summary?: StartResponse['point_summary']
  persisted_messages?: Array<{ role: string; body?: string; content?: string }>
  runtime_links?: CoachRuntimeLinks | null
}

const BASE = '/api/v1/agents/general-coach'

export class GeneralCoachRepository {
  async start(input: StartInput): Promise<StartResponse> {
    return request('POST', BASE + '/start', input)
  }

  async sendMessage(threadId: string, content: string): Promise<MessageResponse> {
    return request('POST', `${BASE}/${threadId}/messages`, { content })
  }

  async close(threadId: string): Promise<CloseResponse> {
    return request('POST', `${BASE}/${threadId}/close`)
  }

  async getState(threadId: string): Promise<StateResponse> {
    return request('GET', `${BASE}/${threadId}/state`)
  }

  async submitFeedback(
    threadId: string,
    body: { turn_index: number; rating: 'up' | 'down'; comment?: string },
  ): Promise<{ ok: boolean }> {
    return request('POST', `${BASE}/${threadId}/feedback`, body)
  }
}

export const generalCoachRepo = new GeneralCoachRepository()

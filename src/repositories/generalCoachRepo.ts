/** GeneralCoachRepository — M19 API calls (start/messages/close/state). */
import { request } from '../api/client'

export interface StartInput {
  initial_question?: string | null
}

export interface StartResponse {
  thread_id: string
  conversation_id: string
  status: string
}

export interface MessageInput {
  content: string
}

export interface MessageResponse {
  thread_id: string
  detected_intent: string | null
  confidence: number | null
  redirect_to: string | null
}

export interface CloseResponse {
  thread_id: string
  status: string
}

export interface StateResponse {
  thread_id: string
  detected_intent: string | null
  message_count: number | null
  session_active: boolean | null
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
}

export const generalCoachRepo = new GeneralCoachRepository()

/** T033 — HTTP Outbox repository interface + implementation.

Used by the React Query hooks and components to interact with the
server-side Outbox replay endpoint.
*/
import { apiClient } from '../api/client'
import type { RequestOptions } from '../api/client'

export interface ReplayEntry {
  client_entry_id: number
  entity_type: string
  operation: string
  entity_id: string
  payload: Record<string, unknown>
  entity_updated_at: string
  client_timestamp: number
}

export interface ReplayResult {
  client_entry_id: number
  status: 'ok' | 'conflict' | 'failed'
  server_entity?: Record<string, unknown>
  conflict_fields?: string[]
  error?: string
}

export interface ReplayResponse {
  results: ReplayResult[]
  summary: {
    total: number
    ok: number
    conflict: number
    failed: number
  }
}

export interface OutboxStatusResponse {
  status: string
  recent_replays: Record<string, unknown>
}

async function request<T>(opts: Omit<RequestOptions, 'path'> & { path: string }): Promise<T> {
  try {
    return await apiClient.request<T>(opts)
  } catch {
    // Fallback for mock mode
    if (import.meta.env.VITE_USE_MOCK === 'true') {
      return mockRequest<T>(opts)
    }
    throw new Error(`Outbox request failed: ${opts.method} ${opts.path}`)
  }
}

function mockRequest<T>(opts: Omit<RequestOptions, 'path'> & { path: string }): T {
  // Return empty success for mock mode
  if (opts.path === '/api/v1/outbox/replay') {
    return {
      results: [],
      summary: { total: 0, ok: 0, conflict: 0, failed: 0 },
    } as unknown as T
  }
  return {
    status: 'healthy',
    recent_replays: { last_hour: 0, conflict_rate: 0 },
  } as unknown as T
}

export const OutboxRepository = {
  async replay(entries: ReplayEntry[]): Promise<ReplayResponse> {
    return request<ReplayResponse>({
      method: 'POST',
      path: '/api/v1/outbox/replay',
      body: { entries },
    })
  },

  async getStatus(): Promise<OutboxStatusResponse> {
    return request<OutboxStatusResponse>({
      method: 'GET',
      path: '/api/v1/outbox/status',
    })
  },
}

export function getOutboxRepository() {
  return OutboxRepository
}

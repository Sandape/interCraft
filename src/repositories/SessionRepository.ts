/**
 * SessionRepository — list / revoke device sessions.
 */
import { apiClient } from '../api/client'
import type { DeviceSession } from '../api/types'

export interface SessionRepository {
  list(): Promise<DeviceSession[]>
  revoke(sessionId: string): Promise<void>
}

export class HttpSessionRepository implements SessionRepository {
  async list(): Promise<DeviceSession[]> {
    return apiClient.request<DeviceSession[]>({
      method: 'GET',
      path: '/api/v1/users/me/sessions',
    })
  }
  async revoke(sessionId: string): Promise<void> {
    await apiClient.request<void>({
      method: 'DELETE',
      path: `/api/v1/users/me/sessions/${sessionId}`,
    })
  }
}

const MOCK_SESSIONS: DeviceSession[] = [
  {
    id: '01900000-0000-7000-8000-000000000aaa',
    device_id: 'dev-aaa',
    device_name: 'Chrome macOS',
    ip: '127.0.0.1',
    user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    created_at: '2026-06-12T10:00:00Z',
    last_seen_at: '2026-06-12T12:00:00Z',
    is_current: true,
  },
  {
    id: '01900000-0000-7000-8000-000000000bbb',
    device_id: 'dev-bbb',
    device_name: 'Safari iPhone',
    ip: '10.0.0.1',
    user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
    created_at: '2026-06-10T08:00:00Z',
    last_seen_at: '2026-06-12T11:00:00Z',
    is_current: false,
  },
]

export class MockSessionRepository implements SessionRepository {
  private sessions: DeviceSession[] = [...MOCK_SESSIONS]
  async list(): Promise<DeviceSession[]> {
    return this.sessions
  }
  async revoke(sessionId: string): Promise<void> {
    this.sessions = this.sessions.filter((s) => s.id !== sessionId)
  }
}

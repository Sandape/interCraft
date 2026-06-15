/** ActivityRepository — cursor-paginated activity feed (M10, US8). */
import { request } from '../api/client'

export interface Activity {
  id: string
  type: string
  actor_type: string
  payload_json: Record<string, unknown>
  occurred_at: string
  created_at: string
}

export interface ActivityList {
  items: Activity[]
  next_cursor: string | null
  has_more: boolean
}

const BASE = '/api/v1/activities'

export abstract class ActivityRepository {
  abstract list(params?: { cursor?: string; limit?: number }): Promise<ActivityList>
}

export class HttpActivityRepository extends ActivityRepository {
  async list(params?: { cursor?: string; limit?: number }): Promise<ActivityList> {
    const q = new URLSearchParams()
    if (params?.cursor) q.set('cursor', params.cursor)
    if (params?.limit) q.set('limit', String(params.limit || 20))
    const qs = q.toString()
    return request('GET', `${BASE}${qs ? `?${qs}` : ''}`)
  }
}

export class MockActivityRepository extends ActivityRepository {
  private store: Activity[] = []

  async list(_params?: { cursor?: string; limit?: number }): Promise<ActivityList> {
    const limit = _params?.limit || 20
    const items = this.store.slice(0, limit)
    return { items, next_cursor: null, has_more: this.store.length > limit }
  }
}

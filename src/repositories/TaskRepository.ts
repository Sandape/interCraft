/** TaskRepository — task CRUD (M10, US8). */
import { request } from '../api/client'

export interface Task {
  id: string
  type: string
  title: string
  description_md: string | null
  status: string
  related_entity_type: string | null
  related_entity_id: string | null
  created_at: string
  updated_at: string
}

const BASE = '/api/v1/tasks'

export abstract class TaskRepository {
  abstract list(params?: { status?: string; limit?: number }): Promise<{ data: Task[] }>
  abstract patch(id: string, patch: Record<string, unknown>): Promise<Task>
  abstract delete(id: string): Promise<void>
}

export class HttpTaskRepository extends TaskRepository {
  async list(params?: { status?: string; limit?: number }): Promise<{ data: Task[] }> {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.limit) q.set('limit', String(params.limit || 50))
    const qs = q.toString()
    return request('GET', `${BASE}${qs ? `?${qs}` : ''}`)
  }

  async patch(id: string, patch: Record<string, unknown>): Promise<Task> {
    return request('PATCH', `${BASE}/${id}`, patch)
  }

  async delete(id: string): Promise<void> {
    return request('DELETE', `${BASE}/${id}`)
  }
}

export class MockTaskRepository extends TaskRepository {
  private store: Task[] = []

  async list(_params?: { status?: string; limit?: number }): Promise<{ data: Task[] }> {
    return { data: this.store }
  }

  async patch(id: string, p: Record<string, unknown>): Promise<Task> {
    const t = this.store.find(t => t.id === id)
    if (!t) throw new Error(`Task ${id} not found`)
    Object.assign(t, p, { updated_at: new Date().toISOString() })
    return t
  }

  async delete(id: string): Promise<void> {
    this.store = this.store.filter(t => t.id !== id)
  }
}

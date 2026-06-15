/** ErrorQuestionRepository — error book CRUD (M08, US6). */
import { request } from '../api/client'
import { errorBook as mockErrors } from '../data/mockData'

export interface ErrorQuestion {
  id: string
  source_session_id: string | null
  dimension: string
  question_text: string
  answer_text: string | null
  status: string
  frequency: number
  score: number
  archived_at: string | null
  created_at: string
  updated_at: string
}

const BASE = '/api/v1/error-questions'

export abstract class ErrorQuestionRepository {
  abstract list(params?: {
    dimension?: string; status?: string; frequency_min?: number; limit?: number
  }): Promise<{ data: ErrorQuestion[]; next_cursor: string | null; has_more: boolean }>
  abstract create(input: {
    question_text: string; dimension?: string; answer_text?: string
  }): Promise<ErrorQuestion>
  abstract get(id: string): Promise<ErrorQuestion>
  abstract patch(id: string, patch: Record<string, unknown>): Promise<ErrorQuestion>
  abstract archive(id: string): Promise<void>
  abstract reset(id: string): Promise<ErrorQuestion>
}

export class HttpErrorQuestionRepository extends ErrorQuestionRepository {
  async list(params?: {
    dimension?: string; status?: string; frequency_min?: number; limit?: number
  }): Promise<{ data: ErrorQuestion[]; next_cursor: string | null; has_more: boolean }> {
    const q = new URLSearchParams()
    if (params?.dimension) q.set('dimension', params.dimension)
    if (params?.status) q.set('status', params.status)
    if (params?.frequency_min !== undefined) q.set('frequency_min', String(params.frequency_min))
    if (params?.limit) q.set('limit', String(params.limit))
    const qs = q.toString()
    return request('GET', `${BASE}${qs ? `?${qs}` : ''}`)
  }

  async create(input: {
    question_text: string; dimension?: string; answer_text?: string
  }): Promise<ErrorQuestion> {
    return request('POST', BASE, input)
  }

  async get(id: string): Promise<ErrorQuestion> {
    return request('GET', `${BASE}/${id}`)
  }

  async patch(id: string, patch: Record<string, unknown>): Promise<ErrorQuestion> {
    return request('PATCH', `${BASE}/${id}`, patch)
  }

  async archive(id: string): Promise<void> {
    return request('DELETE', `${BASE}/${id}`)
  }

  async reset(id: string): Promise<ErrorQuestion> {
    return request('POST', `${BASE}/${id}/reset`)
  }
}

export class MockErrorQuestionRepository extends ErrorQuestionRepository {
  private store: ErrorQuestion[] = mockErrors.map((m: any) => ({
    id: m.id,
    source_session_id: null,
    dimension: m.category || 'algorithm',
    question_text: m.question || '',
    answer_text: m.hint || '',
    status: m.frequency >= 3 ? 'fresh' : m.frequency >= 1 ? 'practicing' : 'mastered',
    frequency: m.frequency || 3,
    score: 0,
    archived_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }))

  async list(params?: {
    dimension?: string; status?: string; limit?: number
  }): Promise<{ data: ErrorQuestion[]; next_cursor: null; has_more: boolean }> {
    let filtered = [...this.store]
    if (params?.dimension) filtered = filtered.filter(e => e.dimension === params.dimension)
    if (params?.status) filtered = filtered.filter(e => e.status === params.status)
    const data = filtered.slice(0, params?.limit || 20)
    return { data, next_cursor: null, has_more: data.length >= (params?.limit || 20) }
  }

  async create(input: {
    question_text: string; dimension?: string
  }): Promise<ErrorQuestion> {
    const eq: ErrorQuestion = {
      id: `eq-${Date.now()}`,
      source_session_id: null,
      dimension: input.dimension || 'algorithm',
      question_text: input.question_text,
      answer_text: '',
      status: 'fresh',
      frequency: 3,
      score: 0,
      archived_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    this.store.unshift(eq)
    return eq
  }

  async get(id: string): Promise<ErrorQuestion> {
    const eq = this.store.find(e => e.id === id)
    if (!eq) throw new Error(`ErrorQuestion ${id} not found`)
    return eq
  }

  async patch(id: string, patch: Record<string, unknown>): Promise<ErrorQuestion> {
    const eq = await this.get(id)
    Object.assign(eq, patch, { updated_at: new Date().toISOString() })
    return eq
  }

  async archive(_id: string): Promise<void> { }

  async reset(id: string): Promise<ErrorQuestion> {
    return this.patch(id, { status: 'fresh', frequency: 3 })
  }
}

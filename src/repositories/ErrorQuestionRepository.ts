/** ErrorQuestionRepository — error book CRUD (M08, US6). */
import { request } from '../api/client'
import { errorBook as mockErrors } from '../data/mockData'

export interface ErrorQuestion {
  id: string
  source_session_id: string | null
  source_question_id: string | null
  dimension: string | null
  question_text: string
  answer_text: string | null
  reference_answer_md: string | null
  status: string
  frequency: number
  score: number | null
  tags: string[] | null
  archived_at: string | null
  last_practiced_at: string | null
  created_at: string
  updated_at: string
}

const BASE = '/api/v1/error-questions'

export abstract class ErrorQuestionRepository {
  abstract list(params?: {
    dimension?: string; status?: string; frequency_min?: number; limit?: number; source?: string
  }): Promise<{ data: ErrorQuestion[]; next_cursor: string | null; has_more: boolean }>
  abstract create(input: {
    question_text: string; dimension?: string; answer_text?: string; reference_answer_md?: string; score?: number; tags?: string[]
  }): Promise<ErrorQuestion>
  abstract get(id: string): Promise<ErrorQuestion>
  abstract patch(id: string, patch: Record<string, unknown>): Promise<ErrorQuestion>
  abstract archive(id: string): Promise<void>
  abstract reset(id: string): Promise<ErrorQuestion>
  abstract recall(id: string): Promise<ErrorQuestion>
  abstract clearSource(id: string): Promise<ErrorQuestion>
}

export class HttpErrorQuestionRepository extends ErrorQuestionRepository {
  async list(params?: {
    dimension?: string; status?: string; frequency_min?: number; limit?: number; source?: string
  }): Promise<{ data: ErrorQuestion[]; next_cursor: string | null; has_more: boolean }> {
    const q = new URLSearchParams()
    if (params?.dimension) q.set('dimension', params.dimension)
    if (params?.status) q.set('status', params.status)
    if (params?.frequency_min !== undefined) q.set('frequency_min', String(params.frequency_min))
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.source) q.set('filter[source]', params.source)
    const qs = q.toString()
    return request('GET', `${BASE}${qs ? `?${qs}` : ''}`)
  }

  async create(input: {
    question_text: string; dimension?: string; answer_text?: string; reference_answer_md?: string; score?: number; tags?: string[]
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

  async recall(id: string): Promise<ErrorQuestion> {
    return request('POST', `${BASE}/${id}/recall`)
  }

  async clearSource(id: string): Promise<ErrorQuestion> {
    return request('POST', `${BASE}/${id}/clear-source`)
  }
}

export class MockErrorQuestionRepository extends ErrorQuestionRepository {
  private store: ErrorQuestion[] = mockErrors.map((m: any) => ({
    id: m.id,
    source_session_id: null,
    source_question_id: null,
    dimension: m.category || 'algorithm',
    question_text: m.question || '',
    answer_text: m.hint || '',
    reference_answer_md: null,
    status: m.frequency >= 3 ? 'fresh' : m.frequency >= 1 ? 'practicing' : 'mastered',
    frequency: m.frequency || 3,
    score: 0,
    tags: null,
    archived_at: null,
    last_practiced_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }))

  async list(params?: {
    dimension?: string; status?: string; limit?: number; source?: string
  }): Promise<{ data: ErrorQuestion[]; next_cursor: null; has_more: boolean }> {
    let filtered = [...this.store]
    if (params?.dimension) filtered = filtered.filter(e => e.dimension === params.dimension)
    if (params?.status) filtered = filtered.filter(e => e.status === params.status)
    if (params?.source === 'auto') filtered = filtered.filter(e => e.source_question_id != null)
    else if (params?.source === 'manual') filtered = filtered.filter(e => e.source_question_id == null)
    const data = filtered.slice(0, params?.limit || 20)
    return { data, next_cursor: null, has_more: data.length >= (params?.limit || 20) }
  }

  async create(input: {
    question_text: string; dimension?: string; answer_text?: string; reference_answer_md?: string; score?: number; tags?: string[]
  }): Promise<ErrorQuestion> {
    const now = new Date().toISOString()
    const eq: ErrorQuestion = {
      id: `eq-${Date.now()}`,
      source_session_id: null,
      source_question_id: null,
      dimension: input.dimension || 'algorithm',
      question_text: input.question_text,
      answer_text: input.answer_text || null,
      reference_answer_md: input.reference_answer_md || null,
      status: 'fresh',
      frequency: 3,
      score: input.score ?? null,
      tags: input.tags ?? null,
      archived_at: null,
      last_practiced_at: null,
      created_at: now,
      updated_at: now,
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

  async archive(id: string): Promise<void> {
    this.store = this.store.filter((e) => e.id !== id)
  }

  async reset(id: string): Promise<ErrorQuestion> {
    return this.patch(id, { status: 'fresh', frequency: 3 })
  }

  async recall(id: string): Promise<ErrorQuestion> {
    const eq = await this.get(id)
    if (eq.frequency <= 0 || eq.status === 'mastered') {
      throw new Error('error question already mastered')
    }
    const frequency = Math.max(eq.frequency - 1, 0)
    return this.patch(id, {
      frequency,
      status: frequency === 0 ? 'mastered' : frequency < 3 ? 'practicing' : 'fresh',
      last_practiced_at: new Date().toISOString(),
    })
  }

  async clearSource(id: string): Promise<ErrorQuestion> {
    return this.patch(id, {
      source_session_id: null,
      source_question_id: null,
    })
  }
}

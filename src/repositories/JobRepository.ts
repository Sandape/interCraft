/** JobRepository — job tracking CRUD (M10, US8). */
import { request } from '../api/client'

export interface Job {
  id: string
  company: string
  position: string
  jd_url: string | null
  branch_id: string | null
  status: string
  status_history: { from_status: string; to_status: string; note?: string; changed_at: string }[]
  notes_md: string | null
  // 019 — extended fields
  base_location: string
  requirements_md: string | null
  employment_type: string
  salary_range_text: string | null
  headcount: number | null
  created_at: string
  updated_at: string
}

export interface JobStats {
  counts: Record<string, number>
  total: number
}

export interface JobTimelineEntry {
  from_status: string
  to_status: string
  note?: string
  changed_at: string
}

const BASE = '/api/v1/jobs'

export abstract class JobRepository {
  abstract list(params?: { status?: string; branch_id?: string; limit?: number }): Promise<{ data: Job[]; next_cursor: string | null; has_more: boolean }>
  abstract create(input: { company: string; position: string; jd_url?: string; branch_id?: string; notes_md?: string | null }): Promise<Job>
  abstract get(id: string): Promise<Job>
  abstract patch(id: string, patch: Record<string, unknown>): Promise<Job>
  abstract updateStatus(id: string, to: string, note?: string): Promise<Job>
  abstract delete(id: string): Promise<void>
  abstract stats(): Promise<JobStats>
  abstract timeline(id: string): Promise<{ data: JobTimelineEntry[] }>
}

export class HttpJobRepository extends JobRepository {
  async list(params?: { status?: string; limit?: number }): Promise<{ data: Job[]; next_cursor: null; has_more: boolean }> {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.limit) q.set('limit', String(params.limit))
    const qs = q.toString()
    return request('GET', `${BASE}${qs ? `?${qs}` : ''}`)
  }

  async create(input: { company: string; position: string; jd_url?: string; branch_id?: string; notes_md?: string | null }): Promise<Job> {
    return request('POST', BASE, input)
  }

  async get(id: string): Promise<Job> {
    return request('GET', `${BASE}/${id}`)
  }

  async patch(id: string, patch: Record<string, unknown>): Promise<Job> {
    return request('PATCH', `${BASE}/${id}`, patch)
  }

  async updateStatus(id: string, to: string, note?: string): Promise<Job> {
    return request('PATCH', `${BASE}/${id}/status`, { to, note })
  }

  async delete(id: string): Promise<void> {
    return request('DELETE', `${BASE}/${id}`)
  }

  async stats(): Promise<JobStats> {
    return request('GET', `${BASE}/stats`)
  }

  async timeline(id: string): Promise<{ data: JobTimelineEntry[] }> {
    return request('GET', `${BASE}/${id}/timeline`)
  }
}

export class MockJobRepository extends JobRepository {
  private store: Job[] = []

  async list(_params?: { status?: string; limit?: number }): Promise<{ data: Job[]; next_cursor: null; has_more: boolean }> {
    return { data: this.store, next_cursor: null, has_more: false }
  }

  async create(input: {
    company: string
    position: string
    jd_url?: string
    branch_id?: string
    notes_md?: string | null
    base_location?: string | null
    requirements_md?: string | null
    employment_type?: string
    salary_range_text?: string | null
    headcount?: number | null
  }): Promise<Job> {
    const job: Job = {
      id: `job-${Date.now()}`,
      company: input.company,
      position: input.position,
      jd_url: input.jd_url ?? null,
      branch_id: input.branch_id ?? null,
      status: 'applied',
      status_history: [{ from_status: '', to_status: 'applied', changed_at: new Date().toISOString() }],
      notes_md: input.notes_md ?? null,
      base_location: input.base_location ?? '',
      requirements_md: input.requirements_md ?? null,
      employment_type: input.employment_type ?? 'unspecified',
      salary_range_text: input.salary_range_text ?? null,
      headcount: input.headcount ?? null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    this.store.unshift(job)
    return job
  }

  async get(id: string): Promise<Job> {
    const j = this.store.find(j => j.id === id)
    if (!j) throw new Error(`Job ${id} not found`)
    return j
  }

  async patch(id: string, p: Record<string, unknown>): Promise<Job> {
    const j = await this.get(id)
    Object.assign(j, p, { updated_at: new Date().toISOString() })
    return j
  }

  async updateStatus(id: string, to: string, note?: string): Promise<Job> {
    const j = await this.get(id)
    j.status_history.push({ from_status: j.status, to_status: to, note, changed_at: new Date().toISOString() })
    j.status = to
    j.updated_at = new Date().toISOString()
    return j
  }

  async delete(_id: string): Promise<void> { }

  async stats(): Promise<JobStats> {
    const counts: Record<string, number> = {}
    for (const j of this.store) counts[j.status] = (counts[j.status] || 0) + 1
    return { counts, total: this.store.length }
  }

  async timeline(id: string): Promise<{ data: JobTimelineEntry[] }> {
    const j = await this.get(id)
    return { data: j.status_history }
  }
}

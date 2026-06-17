/**
 * Round-1 API helpers — typed wrappers around the HTTP endpoints used
 * across specs. All methods return parsed JSON; failures throw.
 */
import { expect, type APIRequestContext } from '@playwright/test'
import { API_BASE } from '../fixtures/auth'

export interface JobFixture {
  id: string
  company: string
  position: string
  base_location?: string | null
  requirements_md?: string | null
  employment_type?: string
  salary_range_text?: string | null
  headcount?: number | null
  branch_id?: string | null
}

export interface BranchFixture {
  id: string
  name: string
  company: string
  position: string
}

export interface SessionFixture {
  id: string
  job_id: string | null
  branch_id: string | null
}

export interface ErrorQuestionFixture {
  id: string
  question_text: string
  answer_text?: string | null
  score: number
  source_session_id: string | null
  source_question_id: string | null
  deleted_at?: string | null
}

export function authHeader(token: string): { Authorization: string } {
  return { Authorization: `Bearer ${token}` }
}

export async function createJob(
  request: APIRequestContext,
  token: string,
  body: Partial<JobFixture>,
): Promise<JobFixture> {
  const res = await request.post(`${API_BASE}/api/v1/jobs`, {
    headers: authHeader(token),
    data: body,
  })
  expect([200, 201]).toContain(res.status())
  return (await res.json()) as JobFixture
}

export async function getJob(
  request: APIRequestContext,
  token: string,
  id: string,
): Promise<JobFixture> {
  const res = await request.get(`${API_BASE}/api/v1/jobs/${id}`, {
    headers: authHeader(token),
  })
  expect(res.status()).toBe(200)
  return (await res.json()) as JobFixture
}

export async function patchJob(
  request: APIRequestContext,
  token: string,
  id: string,
  body: Partial<JobFixture>,
): Promise<JobFixture> {
  const res = await request.patch(`${API_BASE}/api/v1/jobs/${id}`, {
    headers: authHeader(token),
    data: body,
  })
  expect(res.status()).toBe(200)
  return (await res.json()) as JobFixture
}

export async function deleteJob(
  request: APIRequestContext,
  token: string,
  id: string,
): Promise<void> {
  const res = await request.delete(`${API_BASE}/api/v1/jobs/${id}`, {
    headers: authHeader(token),
  })
  expect([200, 204]).toContain(res.status())
}

export async function createBranch(
  request: APIRequestContext,
  token: string,
  body: { name: string; company: string; position: string },
): Promise<BranchFixture> {
  // Backend exposes /resume-branches (singular, hyphenated). The 019 spec
  // docs reference /resumes/branches but the implementation disagrees.
  const res = await request.post(`${API_BASE}/api/v1/resume-branches`, {
    headers: authHeader(token),
    data: body,
  })
  expect([200, 201]).toContain(res.status())
  const body1 = (await res.json()) as { branch: BranchFixture } | { data: BranchFixture } | BranchFixture
  if ('branch' in body1) return body1.branch
  if ('data' in body1) return body1.data
  return body1 as BranchFixture
}

export async function createSessionFromJob(
  request: APIRequestContext,
  token: string,
  jobId: string,
  branchId: string,
  position = 'FE',
  company = 'TestCo',
): Promise<SessionFixture> {
  const res = await request.post(`${API_BASE}/api/v1/interview-sessions`, {
    headers: authHeader(token),
    data: { job_id: jobId, branch_id: branchId, position, company },
  })
  expect([200, 201, 202]).toContain(res.status())
  const body = (await res.json()) as { data: SessionFixture } | SessionFixture
  return ('data' in body ? body.data : body) as SessionFixture
}

export async function createErrorQuestion(
  request: APIRequestContext,
  token: string,
  body: {
    question_text: string
    answer_text?: string
    dimension?: string
    score?: number
    /**
     * NOTE: The 019 spec says POST /error-questions should accept
     * `source_session_id` / `source_question_id`, but the Pydantic
     * CreateErrorQuestionInput does not declare those fields. Sending
     * them is silently dropped. We pass them through anyway so we
     * can detect the deviation.
     */
    source_session_id?: string
    source_question_id?: string
  },
): Promise<ErrorQuestionFixture> {
  const res = await request.post(`${API_BASE}/api/v1/error-questions`, {
    headers: authHeader(token),
    data: body,
  })
  expect([200, 201]).toContain(res.status())
  return (await res.json()) as ErrorQuestionFixture
}

export async function listErrorQuestions(
  request: APIRequestContext,
  token: string,
  params: { source?: 'auto' | 'manual' | 'all' } = {},
): Promise<ErrorQuestionFixture[]> {
  const qs = params.source ? `?filter[source]=${params.source}` : ''
  const res = await request.get(`${API_BASE}/api/v1/error-questions${qs}`, {
    headers: authHeader(token),
  })
  expect(res.status()).toBe(200)
  const body = (await res.json()) as { data: ErrorQuestionFixture[] } | ErrorQuestionFixture[]
  return (Array.isArray(body) ? body : body.data) as ErrorQuestionFixture[]
}

export async function clearErrorSource(
  request: APIRequestContext,
  token: string,
  id: string,
): Promise<ErrorQuestionFixture> {
  // 020 (FIX-004, D-003): the implementation is now PATCH to match the
  // 019 contract. POST would return 405 Method Not Allowed.
  const res = await request.patch(`${API_BASE}/api/v1/error-questions/${id}/clear-source`, {
    headers: authHeader(token),
  })
  expect(res.status()).toBe(200)
  return (await res.json()) as ErrorQuestionFixture
}

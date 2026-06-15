/** ErrorQuestionRepository MSW tests (US6). */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  // GET /error-questions
  http.get('/api/v1/error-questions', () =>
    HttpResponse.json({
      data: [
        {
          id: '00000000-0000-7000-8000-000000000010',
          source_session_id: null,
          dimension: 'algorithm',
          question_text: 'What is the time complexity of quicksort?',
          answer_text: 'O(n log n) average, O(n²) worst',
          status: 'fresh',
          frequency: 3,
          score: 0,
          archived_at: null,
          created_at: '2026-06-13T00:00:00Z',
          updated_at: '2026-06-13T00:00:00Z',
        },
      ],
      next_cursor: null,
      has_more: false,
    })
  ),
  // POST /error-questions
  http.post('/api/v1/error-questions', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: '00000000-0000-7000-8000-000000000011',
      source_session_id: null,
      dimension: body.dimension || 'algorithm',
      question_text: body.question_text,
      answer_text: (body.answer_text as string) || '',
      status: 'fresh',
      frequency: 3,
      score: 0,
      archived_at: null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  }),
  // GET /error-questions/:id
  http.get('/api/v1/error-questions/:id', ({ params }) =>
    HttpResponse.json({
      id: params.id as string,
      source_session_id: null,
      dimension: 'system_design',
      question_text: 'How do you design a URL shortener?',
      answer_text: '',
      status: 'practicing',
      frequency: 2,
      score: 0,
      archived_at: null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  ),
  // PATCH /error-questions/:id
  http.patch('/api/v1/error-questions/:id', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: params.id as string,
      source_session_id: null,
      dimension: 'algorithm',
      question_text: 'test',
      answer_text: '',
      status: body.status || 'fresh',
      frequency: body.frequency ?? 3,
      score: 0,
      archived_at: null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  }),
  // DELETE /error-questions/:id
  http.delete('/api/v1/error-questions/:id', () =>
    new HttpResponse(null, { status: 204 })
  ),
  // POST /error-questions/:id/reset
  http.post('/api/v1/error-questions/:id/reset', ({ params }) =>
    HttpResponse.json({
      id: params.id as string,
      source_session_id: null,
      dimension: 'algorithm',
      question_text: 'test',
      answer_text: '',
      status: 'fresh',
      frequency: 3,
      score: 0,
      archived_at: null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())

describe('ErrorQuestionRepository', () => {
  it('lists error questions', async () => {
    const resp = await fetch('/api/v1/error-questions?dimension=algorithm')
    const json = await resp.json() as { data: unknown[] }
    expect(resp.status).toBe(200)
    expect(json.data).toHaveLength(1)
    expect((json.data[0] as Record<string, unknown>).dimension).toBe('algorithm')
  })

  it('creates an error question', async () => {
    const resp = await fetch('/api/v1/error-questions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question_text: 'New error?', dimension: 'algorithm' }),
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.status).toBe('fresh')
    expect(json.frequency).toBe(3)
  })

  it('gets a single error question', async () => {
    const resp = await fetch('/api/v1/error-questions/00000000-0000-7000-8000-000000000010')
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.dimension).toBe('system_design')
  })

  it('patches an error question', async () => {
    const resp = await fetch('/api/v1/error-questions/00000000-0000-7000-8000-000000000010', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'mastered', frequency: 1 }),
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.status).toBe('mastered')
    expect(json.frequency).toBe(1)
  })

  it('archives an error question', async () => {
    const resp = await fetch('/api/v1/error-questions/00000000-0000-7000-8000-000000000010', {
      method: 'DELETE',
    })
    expect(resp.status).toBe(204)
  })

  it('resets an error question', async () => {
    const resp = await fetch('/api/v1/error-questions/00000000-0000-7000-8000-000000000010/reset', {
      method: 'POST',
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.status).toBe('fresh')
    expect(json.frequency).toBe(3)
  })
})

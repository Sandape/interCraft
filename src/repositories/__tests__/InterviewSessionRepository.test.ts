/** InterviewSessionRepository MSW tests (US4 partial, M11). */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  // GET /interview-sessions
  http.get('/api/v1/interview-sessions', () =>
    HttpResponse.json({
      data: [
        {
          id: '00000000-0000-7000-8000-000000000050',
          mode: 'text',
          status: 'completed',
          score: 85,
          duration_seconds: 1800,
          question_count: 10,
          thread_id: null,
          created_at: '2026-06-13T00:00:00Z',
          updated_at: '2026-06-13T00:00:00Z',
        },
      ],
    })
  ),
  // GET /interview-sessions/:id
  http.get('/api/v1/interview-sessions/:id', ({ params }) =>
    HttpResponse.json({
      id: params.id as string,
      mode: 'voice',
      status: 'in_progress',
      score: null,
      duration_seconds: 600,
      question_count: 5,
      thread_id: null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())

describe('InterviewSessionRepository', () => {
  it('lists interview sessions', async () => {
    const resp = await fetch('/api/v1/interview-sessions')
    const json = await resp.json() as { data: unknown[] }
    expect(resp.status).toBe(200)
    expect(json.data).toHaveLength(1)
    expect((json.data[0] as Record<string, unknown>).mode).toBe('text')
  })

  it('gets a single interview session', async () => {
    const resp = await fetch('/api/v1/interview-sessions/00000000-0000-7000-8000-000000000050')
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.mode).toBe('voice')
    expect(json.status).toBe('in_progress')
  })

  it('returns null thread_id (Phase 4 placeholder)', async () => {
    const resp = await fetch('/api/v1/interview-sessions/00000000-0000-7000-8000-000000000050')
    const json = await resp.json() as Record<string, unknown>
    expect(json.thread_id).toBeNull()
  })
})

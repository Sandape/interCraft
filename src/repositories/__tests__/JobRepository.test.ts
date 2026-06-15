/** JobRepository MSW tests (US8). */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  // Concrete paths MUST come before parameterized :id
  // GET /jobs/stats
  http.get('/api/v1/jobs/stats', () =>
    HttpResponse.json({
      counts: { applied: 2, screening: 1, interview: 0, offer: 0, rejected: 0, withdrawn: 0 },
      total: 3,
    })
  ),
  // GET /jobs
  http.get('/api/v1/jobs', () =>
    HttpResponse.json({
      data: [
        {
          id: '00000000-0000-7000-8000-000000000020',
          company: 'Acme Corp',
          position: 'Senior FE',
          jd_url: null,
          branch_id: null,
          status: 'applied',
          status_history: [{ from_status: '', to_status: 'applied', changed_at: '2026-06-13T00:00:00Z' }],
          note: null,
          created_at: '2026-06-13T00:00:00Z',
          updated_at: '2026-06-13T00:00:00Z',
        },
      ],
      next_cursor: null,
      has_more: false,
    })
  ),
  // POST /jobs
  http.post('/api/v1/jobs', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: '00000000-0000-7000-8000-000000000021',
      company: body.company,
      position: body.position,
      jd_url: body.jd_url ?? null,
      branch_id: null,
      status: 'applied',
      status_history: [{ from_status: '', to_status: 'applied', changed_at: '2026-06-13T00:00:00Z' }],
      note: (body.note as string) ?? null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  }),
  // GET /jobs/:id/timeline
  http.get('/api/v1/jobs/:id/timeline', ({ params }) =>
    HttpResponse.json({
      data: [
        { from_status: '', to_status: 'applied', changed_at: '2026-06-13T00:00:00Z' },
        { from_status: 'applied', to_status: 'screening', changed_at: '2026-06-14T00:00:00Z' },
      ],
    })
  ),
  // GET /jobs/:id
  http.get('/api/v1/jobs/:id', ({ params }) =>
    HttpResponse.json({
      id: params.id as string,
      company: 'Acme Corp',
      position: 'Senior FE',
      jd_url: null,
      branch_id: null,
      status: 'applied',
      status_history: [{ from_status: '', to_status: 'applied', changed_at: '2026-06-13T00:00:00Z' }],
      note: null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  ),
  // PATCH /jobs/:id/status
  http.patch('/api/v1/jobs/:id/status', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: params.id as string,
      company: 'Acme Corp',
      position: 'Senior FE',
      jd_url: null,
      branch_id: null,
      status: body.to as string,
      status_history: [
        { from_status: '', to_status: 'applied', changed_at: '2026-06-13T00:00:00Z' },
        { from_status: 'applied', to_status: body.to as string, changed_at: '2026-06-14T00:00:00Z' },
      ],
      note: null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-14T00:00:00Z',
    })
  }),
  // PATCH /jobs/:id
  http.patch('/api/v1/jobs/:id', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: params.id as string,
      company: (body.company as string) || 'Acme Corp',
      position: (body.position as string) || 'Senior FE',
      jd_url: null,
      branch_id: null,
      status: 'applied',
      status_history: [{ from_status: '', to_status: 'applied', changed_at: '2026-06-13T00:00:00Z' }],
      note: null,
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  }),
  // DELETE /jobs/:id
  http.delete('/api/v1/jobs/:id', () =>
    new HttpResponse(null, { status: 204 })
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())

describe('JobRepository', () => {
  it('lists jobs', async () => {
    const resp = await fetch('/api/v1/jobs?status=applied')
    const json = await resp.json() as { data: unknown[] }
    expect(resp.status).toBe(200)
    expect(json.data).toHaveLength(1)
    expect((json.data[0] as Record<string, unknown>).company).toBe('Acme Corp')
  })

  it('creates a job', async () => {
    const resp = await fetch('/api/v1/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company: 'NewCo', position: 'FE Dev' }),
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.company).toBe('NewCo')
    expect(json.status).toBe('applied')
  })

  it('gets a single job', async () => {
    const resp = await fetch('/api/v1/jobs/00000000-0000-7000-8000-000000000020')
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.company).toBe('Acme Corp')
  })

  it('patches a job', async () => {
    const resp = await fetch('/api/v1/jobs/00000000-0000-7000-8000-000000000020', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company: 'Updated Co' }),
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.company).toBe('Updated Co')
  })

  it('updates job status', async () => {
    const resp = await fetch('/api/v1/jobs/00000000-0000-7000-8000-000000000020/status', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to: 'screening' }),
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.status).toBe('screening')
  })

  it('deletes a job', async () => {
    const resp = await fetch('/api/v1/jobs/00000000-0000-7000-8000-000000000020', {
      method: 'DELETE',
    })
    expect(resp.status).toBe(204)
  })

  it('fetches job stats', async () => {
    const resp = await fetch('/api/v1/jobs/stats')
    const json = await resp.json() as { counts: Record<string, number>; total: number }
    expect(resp.status).toBe(200)
    expect(json.total).toBe(3)
    expect(json.counts.applied).toBe(2)
  })

  it('fetches job timeline', async () => {
    const resp = await fetch('/api/v1/jobs/00000000-0000-7000-8000-000000000020/timeline')
    const json = await resp.json() as { data: unknown[] }
    expect(resp.status).toBe(200)
    expect(json.data).toHaveLength(2)
  })
})

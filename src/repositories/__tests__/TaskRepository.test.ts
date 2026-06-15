/** TaskRepository MSW tests (US8). */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  // GET /tasks
  http.get('/api/v1/tasks', () =>
    HttpResponse.json({
      data: [
        {
          id: '00000000-0000-7000-8000-000000000030',
          type: 'interview_prep',
          title: '准备 Acme Corp 面试',
          description_md: null,
          status: 'todo',
          related_entity_type: 'job',
          related_entity_id: '00000000-0000-7000-8000-000000000020',
          created_at: '2026-06-13T00:00:00Z',
          updated_at: '2026-06-13T00:00:00Z',
        },
      ],
    })
  ),
  // PATCH /tasks/:id
  http.patch('/api/v1/tasks/:id', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: params.id as string,
      type: 'interview_prep',
      title: '准备 Acme Corp 面试',
      description_md: null,
      status: body.status || 'doing',
      related_entity_type: 'job',
      related_entity_id: '00000000-0000-7000-8000-000000000020',
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  }),
  // DELETE /tasks/:id
  http.delete('/api/v1/tasks/:id', () =>
    new HttpResponse(null, { status: 204 })
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())

describe('TaskRepository', () => {
  it('lists tasks', async () => {
    const resp = await fetch('/api/v1/tasks?status=todo')
    const json = await resp.json() as { data: unknown[] }
    expect(resp.status).toBe(200)
    expect(json.data).toHaveLength(1)
    expect((json.data[0] as Record<string, unknown>).type).toBe('interview_prep')
  })

  it('patches a task status', async () => {
    const resp = await fetch('/api/v1/tasks/00000000-0000-7000-8000-000000000030', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'doing' }),
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.status).toBe('doing')
  })

  it('deletes a task', async () => {
    const resp = await fetch('/api/v1/tasks/00000000-0000-7000-8000-000000000030', {
      method: 'DELETE',
    })
    expect(resp.status).toBe(204)
  })
})

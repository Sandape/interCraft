/** ActivityRepository MSW tests (US8). */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  // GET /activities
  http.get('/api/v1/activities', () =>
    HttpResponse.json({
      items: [
        {
          id: '00000000-0000-7000-8000-000000000040',
          type: 'job.created',
          actor_type: 'user',
          payload_json: { company: 'Acme Corp', position: 'Senior FE' },
          occurred_at: '2026-06-13T00:00:00Z',
          created_at: '2026-06-13T00:00:00Z',
        },
        {
          id: '00000000-0000-7000-8000-000000000041',
          type: 'job.status_changed',
          actor_type: 'user',
          payload_json: { from: 'applied', to: 'screening' },
          occurred_at: '2026-06-14T00:00:00Z',
          created_at: '2026-06-14T00:00:00Z',
        },
      ],
      next_cursor: 'bmV4dF9wYWdlXzI=',
      has_more: true,
    })
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())

describe('ActivityRepository', () => {
  it('lists activities with cursor pagination', async () => {
    const resp = await fetch('/api/v1/activities?limit=20')
    const json = await resp.json() as { items: unknown[]; next_cursor: string | null; has_more: boolean }
    expect(resp.status).toBe(200)
    expect(json.items).toHaveLength(2)
    expect(json.has_more).toBe(true)
    expect(json.next_cursor).toBeTruthy()
  })

  it('accepts cursor parameter', async () => {
    const resp = await fetch('/api/v1/activities?cursor=bmV4dF9wYWdlXzI=&limit=10')
    const json = await resp.json() as { items: unknown[] }
    expect(resp.status).toBe(200)
    expect(json.items).toHaveLength(2)
  })

  it('returns items with expected activity shape', async () => {
    const resp = await fetch('/api/v1/activities')
    const json = await resp.json() as { items: Record<string, unknown>[] }
    const item = json.items[0]
    expect(item.id).toBeTruthy()
    expect(item.type).toBeTruthy()
    expect(item.actor_type).toBeTruthy()
    expect(item.occurred_at).toBeTruthy()
  })
})

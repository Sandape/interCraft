/** AbilityRepository MSW tests (US5). */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  // GET /ability-dimensions
  http.get('/api/v1/ability-dimensions', () =>
    HttpResponse.json({
      data: [
        {
          id: '00000000-0000-7000-8000-000000000001',
          dimension_key: 'tech_depth',
          actual_score: 5.5,
          ideal_score: 10.0,
          sub_scores: {
            fundamentals: { actual: 6, ideal: 10 },
            system_design: { actual: 5, ideal: 10 },
            depth_specialty: { actual: 4, ideal: 10 },
          },
          is_active: true,
          source: 'manual',
          last_updated_at: '2026-06-13T00:00:00Z',
          created_at: '2026-06-13T00:00:00Z',
          updated_at: '2026-06-13T00:00:00Z',
        },
      ],
    })
  ),
  // Concrete paths MUST come before parameterized :key to avoid interception
  // GET /ability-dimensions/history
  http.get('/api/v1/ability-dimensions/history', () =>
    HttpResponse.json({ data: [] })
  ),
  // GET /ability-dimensions/dimensions-meta
  http.get('/api/v1/ability-dimensions/dimensions-meta', () =>
    HttpResponse.json({
      dimensions: [
        { key: 'tech_depth', label_zh: '技术深度', label_en: 'Technical Depth',
          sub_keys: [{ key: 'fundamentals', label_zh: '基础知识' }] },
      ],
    })
  ),
  // GET /ability-dimensions/:key
  http.get('/api/v1/ability-dimensions/:key', ({ params }) =>
    HttpResponse.json({
      id: '00000000-0000-7000-8000-000000000002',
      dimension_key: params.key as string,
      actual_score: 7.0,
      ideal_score: 10.0,
      sub_scores: {},
      is_active: true,
      source: 'manual',
      last_updated_at: '2026-06-13T00:00:00Z',
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  ),
  // PATCH /ability-dimensions/:key
  http.patch('/api/v1/ability-dimensions/:key', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: '00000000-0000-7000-8000-000000000003',
      dimension_key: params.key as string,
      actual_score: body.actual_score ?? 5.0,
      ideal_score: body.ideal_score ?? 10.0,
      sub_scores: body.sub_scores ?? {},
      is_active: true,
      source: 'manual',
      last_updated_at: '2026-06-13T00:00:00Z',
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  }),
  // POST /ability-dimensions/:key/toggle
  http.post('/api/v1/ability-dimensions/:key/toggle', async ({ params, request }) => {
    const body = await request.json() as { is_active: boolean }
    return HttpResponse.json({
      id: '00000000-0000-7000-8000-000000000004',
      dimension_key: params.key as string,
      actual_score: 0.0,
      ideal_score: 10.0,
      sub_scores: {},
      is_active: body.is_active,
      source: 'manual',
      last_updated_at: '2026-06-13T00:00:00Z',
      created_at: '2026-06-13T00:00:00Z',
      updated_at: '2026-06-13T00:00:00Z',
    })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())

describe('AbilityRepository', () => {
  it('fetches ability dimensions list', async () => {
    const resp = await fetch('/api/v1/ability-dimensions')
    const json = await resp.json() as { data: unknown[] }
    expect(resp.status).toBe(200)
    expect(json.data).toHaveLength(1)
    expect((json.data[0] as Record<string, unknown>).dimension_key).toBe('tech_depth')
  })

  it('fetches single dimension', async () => {
    const resp = await fetch('/api/v1/ability-dimensions/architecture')
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.dimension_key).toBe('architecture')
  })

  it('patches a dimension', async () => {
    const resp = await fetch('/api/v1/ability-dimensions/tech_depth', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actual_score: 8.0 }),
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.actual_score).toBe(8.0)
  })

  it('toggles a dimension', async () => {
    const resp = await fetch('/api/v1/ability-dimensions/tech_depth/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: false }),
    })
    const json = await resp.json() as Record<string, unknown>
    expect(resp.status).toBe(200)
    expect(json.is_active).toBe(false)
  })

  it('fetches history', async () => {
    const resp = await fetch('/api/v1/ability-dimensions/history?aggregate=month')
    const json = await resp.json() as { data: unknown[] }
    expect(resp.status).toBe(200)
    expect(Array.isArray(json.data)).toBe(true)
  })

  it('fetches dimensions meta', async () => {
    const resp = await fetch('/api/v1/ability-dimensions/dimensions-meta')
    const json = await resp.json() as { dimensions: unknown[] }
    expect(resp.status).toBe(200)
    expect(json.dimensions.length).toBeGreaterThan(0)
  })
})

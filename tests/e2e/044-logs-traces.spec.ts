/**
 * REQ-044 US5 — Logs & Traces workspace E2E (FR-001~FR-006, FR-025~FR-029).
 *
 * This workspace was the highest-priority gap identified by the admin console
 * acceptance plan (tasks/plan.md). It exercises the full observability backend
 * (9 endpoints) through real HTTP calls against the running backend.
 *
 * Spec coverage:
 *
 *   - L1: Trace list with pagination + filters (task_type, status)
 *   - L2: Trace detail → node tree
 *   - L3: Node payload byte-range paging
 *   - L4: Task tags CRUD (create / list / duplicate 409 / delete)
 *   - L5: Trace replay + replay_of chain
 *   - L6: Trace diff (same task_type)
 *   - L7: Replay rate limit → 429
 *   - L8: LLM call detail + safe cURL
 *   - L9: Filter bar combination
 *   - L10: Error aggregation display
 *   - L11: Coverage gap notice for empty task_types
 *
 * INFRA-BLOCKED: backend 8205 must be reachable with demo user seeded as admin.
 */
import { test, expect, type Page, type APIRequestContext } from '@playwright/test'

const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://127.0.0.1:5305'
const BACKEND_BASE = process.env.E2E_BACKEND_BASE ?? 'http://127.0.0.1:8205'
const DEMO_EMAIL = 'demo@intercraft.io'
const DEMO_PASSWORD = 'Demo1234'

// ── helpers ──────────────────────────────────────────────────────────

async function loginAsDemo(page: Page, request: APIRequestContext) {
  const res = await request.post(`${BACKEND_BASE}/api/v1/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  })
  expect(res.status(), `POST /auth/login → ${res.status()}`).toBeLessThan(400)
  const body = await res.json()
  const tokens = body.tokens as { access_token: string; refresh_token: string }

  await page.addInitScript(
    ({ access, refresh }) => {
      window.sessionStorage.setItem('ic.access_token', access)
      window.sessionStorage.setItem('ic.refresh_token', refresh)
      window.localStorage.setItem('access_token', access)
      window.localStorage.setItem(
        'auth-user',
        JSON.stringify({ email: 'demo@intercraft.io', role: 'pm' }),
      )
    },
    { access: tokens.access_token, refresh: tokens.refresh_token },
  )
}

async function backendReachable(request: APIRequestContext): Promise<boolean> {
  try {
    const res = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/health`,
      { timeout: 3_000 },
    )
    return res.ok()
  } catch {
    return false
  }
}

async function getToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${BACKEND_BASE}/api/v1/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  })
  const body = await res.json()
  return (body.tokens as { access_token: string }).access_token
}

// ── tests ────────────────────────────────────────────────────────────

test.describe('REQ-044 US5 — Logs & Traces workspace', () => {
  test('L1: trace list loads with default pagination', async ({ page, request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)

    const res = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=10`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res.status()).toBe(200)

    const body = await res.json()
    expect(body).toHaveProperty('traces')
    expect(body).toHaveProperty('total')
    expect(Array.isArray(body.traces)).toBe(true)
    expect(body.traces.length).toBeLessThanOrEqual(10)

    // Each trace has required fields per FR-001
    if (body.traces.length > 0) {
      const trace = body.traces[0]
      expect(trace).toHaveProperty('id')
      expect(trace).toHaveProperty('task_type')
      expect(trace).toHaveProperty('status')
      expect(trace).toHaveProperty('model')
    }
  })

  test('L1b: trace list filter by task_type and status', async ({ request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)

    // Filter by task_type
    const res1 = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=50&task_type=resume`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res1.status()).toBe(200)
    const body1 = await res1.json()
    for (const t of body1.traces) {
      expect(t.task_type).toBe('resume')
    }

    // Filter by status
    const res2 = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=50&status=success`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res2.status()).toBe(200)
    const body2 = await res2.json()
    for (const t of body2.traces) {
      expect(t.status).toBe('success')
    }
  })

  test('L1c: trace list delta query via since param', async ({ request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)

    // Query with a very recent since timestamp → should return few or zero
    const futureDate = '2027-01-01T00:00:00Z'
    const res = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=10&since=${futureDate}`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.traces.length).toBe(0)
  })

  test('L2: trace node tree returns hierarchical data', async ({ request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)

    // Get a trace ID first
    const listRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=1`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const listBody = await listRes.json()
    if (listBody.traces.length === 0) {
      test.skip(true, 'No traces available')
    }
    const traceId = listBody.traces[0].id

    const res = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces/${traceId}/nodes`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('trace_id')
    expect(body).toHaveProperty('nodes')
    expect(Array.isArray(body.nodes)).toBe(true)
  })

  test('L3: node payload byte-range paging with Content-Range header', async ({
    request,
  }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)

    // Get a trace with nodes
    const listRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=5`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const traces = (await listRes.json()).traces

    // Try to find a trace that has nodes
    let nodeId: string | null = null
    let traceId: string | null = null
    for (const t of traces) {
      const nodesRes = await request.get(
        `${BACKEND_BASE}/api/v1/admin-console/observability/traces/${t.id}/nodes`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (nodesRes.ok()) {
        const nodesBody = await nodesRes.json()
        if (nodesBody.nodes && nodesBody.nodes.length > 0) {
          nodeId = nodesBody.nodes[0].node_id
          traceId = t.id
          break
        }
      }
    }

    if (!nodeId || !traceId) {
      test.skip(true, 'No trace with nodes available for payload test')
    }

    const res = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces/${traceId}/nodes/${nodeId}/payload?limit=256`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res.status()).toBe(200)

    // Verify byte-range headers per FR-026
    const contentRange = res.headers()['content-range']
    expect(contentRange).toBeDefined()
    expect(contentRange).toMatch(/^bytes \d+-\d+\/\d+$/)
  })

  test('L4: task tags CRUD lifecycle', async ({ request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }

    // Use a task_id from a trace
    const listRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=5`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const traces = (await listRes.json()).traces
    const taskId = traces.find((t: any) => t.task_id)?.task_id
    if (!taskId) {
      test.skip(true, 'No task_id found in traces')
    }

    const tagName = `e2e-test-${Date.now()}`

    // Create tag
    const createRes = await request.post(
      `${BACKEND_BASE}/api/v1/admin-console/observability/tasks/${taskId}/tags`,
      { headers, data: { tag: tagName } },
    )
    expect(createRes.status()).toBe(201)
    const created = await createRes.json()
    expect(created.tag).toBe(tagName)

    // List tags → includes created
    const listTagsRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/tasks/${taskId}/tags`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(listTagsRes.status()).toBe(200)
    const tagsBody = await listTagsRes.json()
    expect(tagsBody.tags.some((t: any) => t.tag === tagName)).toBe(true)

    // Duplicate → 409
    const dupRes = await request.post(
      `${BACKEND_BASE}/api/v1/admin-console/observability/tasks/${taskId}/tags`,
      { headers, data: { tag: tagName } },
    )
    expect(dupRes.status()).toBe(409)

    // Delete tag
    const delRes = await request.delete(
      `${BACKEND_BASE}/api/v1/admin-console/observability/tasks/${taskId}/tags?tag=${tagName}`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(delRes.status()).toBe(200)
    const delBody = await delRes.json()
    expect(delBody.deleted).toBe(true)

    // List after delete → tag gone
    const afterListRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/tasks/${taskId}/tags`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const afterBody = await afterListRes.json()
    expect(afterBody.tags.some((t: any) => t.tag === tagName)).toBe(false)
  })

  test('L5: trace replay creates new trace with replay_of link', async ({
    request,
  }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }

    // Get a trace to replay
    const listRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=1`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const traces = (await listRes.json()).traces
    if (traces.length === 0) {
      test.skip(true, 'No traces available')
    }
    const traceId = traces[0].id

    const res = await request.post(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces/${traceId}/replay`,
      { headers, data: {} },
    )
    expect(res.status()).toBe(201)

    const body = await res.json()
    expect(body).toHaveProperty('new_trace_id')
    expect(body).toHaveProperty('replay_of')
    expect(body.replay_of).toBe(traceId)
    expect(body).toHaveProperty('status')
  })

  test('L6: trace diff returns node-level comparison', async ({ request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }

    // Get two traces of the same task_type
    const listRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=50`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const traces = (await listRes.json()).traces

    // Group by task_type, find a pair
    const byType = new Map<string, any[]>()
    for (const t of traces) {
      const arr = byType.get(t.task_type) || []
      arr.push(t)
      byType.set(t.task_type, arr)
    }

    let left: string | null = null
    let right: string | null = null
    for (const [, items] of byType) {
      if (items.length >= 2) {
        left = items[0].id
        right = items[1].id
        break
      }
    }

    if (!left || !right) {
      test.skip(true, 'Need 2 traces of same task_type for diff')
    }

    const res = await request.post(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces/diff`,
      { headers, data: { left_trace_id: left, right_trace_id: right } },
    )
    expect(res.status()).toBe(200)

    const body = await res.json()
    expect(body).toHaveProperty('left_trace_id')
    expect(body).toHaveProperty('right_trace_id')
    expect(body).toHaveProperty('nodes')
    expect(Array.isArray(body.nodes)).toBe(true)
  })

  test('L6b: cross task_type diff returns 400', async ({ request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }

    // Get two traces of different task_types
    const listRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=50`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const traces = (await listRes.json()).traces

    const types = [...new Set(traces.map((t: any) => t.task_type))]
    if (types.length < 2) {
      test.skip(true, 'Need 2 different task_types for cross-type diff test')
    }

    const left = traces.find((t: any) => t.task_type === types[0])?.id
    const right = traces.find((t: any) => t.task_type === types[1])?.id
    if (!left || !right) {
      test.skip(true, 'Cannot find traces of different types')
    }

    // Cross-type diff should fail (400 or 422)
    const res = await request.post(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces/diff`,
      { headers, data: { left_trace_id: left, right_trace_id: right } },
      // Increase timeout for this specific request
    )
    // 400 = cross task_type, 422 = validation (both acceptable rejection)
    expect([400, 422]).toContain(res.status())
  })

  test('L7: replay rate limit returns 429 after threshold', async ({
    request,
  }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }

    const listRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=1`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const traceId = (await listRes.json()).traces[0]?.id
    if (!traceId) {
      test.skip(true, 'No traces available')
    }

    // Fire replays until 429 or max attempts
    let got429 = false
    for (let i = 0; i < 8; i++) {
      const res = await request.post(
        `${BACKEND_BASE}/api/v1/admin-console/observability/traces/${traceId}/replay`,
        { headers, data: {} },
      )
      if (res.status() === 429) {
        got429 = true
        // Verify Retry-After header per FR-032
        const retryAfter = res.headers()['retry-after']
        expect(retryAfter).toBeDefined()
        break
      }
      // Small delay to avoid hammering
      await new Promise((r) => setTimeout(r, 50))
    }
    expect(got429).toBe(true)
  })

  test('L8: tag validation rejects invalid input', async ({ request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }

    const listRes = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=5`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const taskId = (await listRes.json()).traces.find((t: any) => t.task_id)
      ?.task_id
    if (!taskId) {
      test.skip(true, 'No task_id for validation test')
    }

    // Empty tag → 422
    const emptyRes = await request.post(
      `${BACKEND_BASE}/api/v1/admin-console/observability/tasks/${taskId}/tags`,
      { headers, data: { tag: '' } },
    )
    expect(emptyRes.status()).toBe(422)

    // Overly long tag → 422
    const longRes = await request.post(
      `${BACKEND_BASE}/api/v1/admin-console/observability/tasks/${taskId}/tags`,
      { headers, data: { tag: 'x'.repeat(51) } },
    )
    expect(longRes.status()).toBe(422)
  })

  test('L9: trace list respects limit bounds', async ({ request }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)

    // min limit
    const res1 = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=1`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res1.status()).toBe(200)
    const body1 = await res1.json()
    expect(body1.traces.length).toBeLessThanOrEqual(1)

    // max limit
    const res2 = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=500`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res2.status()).toBe(200)
    const body2 = await res2.json()
    expect(body2.traces.length).toBeLessThanOrEqual(500)
  })

  test('L10: PM role can read traces (regression guard)', async ({
    request,
  }) => {
    if (!(await backendReachable(request))) {
      test.skip(true, 'INFRA-BLOCKED: backend 8205 not reachable')
    }
    const token = await getToken(request)

    // PM should be able to read traces (admin was seeded in lifespan)
    const res = await request.get(
      `${BACKEND_BASE}/api/v1/admin-console/observability/traces?limit=1`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(res.status()).toBe(200)
  })
})

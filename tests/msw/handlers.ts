/**
 * MSW handlers — mirror the backend contracts in
 * `specs/001-intercraft-product-spec/contracts/`. Used by frontend
 * repository unit tests and Vitest integration tests.
 */
import { http, HttpResponse } from 'msw'

const MOCK_USER = {
  id: '01900000-0000-7000-8000-000000000001',
  email: 'demo@intercraft.io',
  display_name: 'Demo 用户',
  title: '前端工程师',
  years_of_experience: 3,
  target_role: '高级前端工程师',
  bio: null,
  avatar_url: null,
  subscription: 'free',
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-12T00:00:00Z',
}

const TOKENS = {
  access_token: 'mock-access-token',
  refresh_token: 'mock-refresh-token',
  token_type: 'Bearer' as const,
  expires_in: 900,
}

const BRANCHES = [
  {
    id: '01900000-0000-7000-8000-000000000m01',
    user_id: MOCK_USER.id,
    parent_id: null,
    name: '主简历',
    is_main: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-12T00:00:00Z',
    last_edited_at: '2026-06-12T11:30:00Z',
  },
]

const BLOCKS = [
  {
    id: '01900000-0000-7000-8000-000000000b01',
    branch_id: BRANCHES[0].id,
    type: 'heading' as const,
    title: '个人信息',
    content_md: '# Demo',
    order_index: 'a0',
    meta: {},
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-12T00:00:00Z',
  },
]

const SESSION_BODY = {
  id: 'mock-session-1',
  user_id: MOCK_USER.id,
  branch_id: null,
  position: null,
  company: null,
  mode: 'text',
  status: 'pending',
  thread_id: null,
  job_id: null,
  overall_score: null,
  score: null,
  duration_seconds: null,
  duration_sec: null,
  question_count: null,
  started_at: null,
  ended_at: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  base_location: null,
  requirements_md: null,
}

export const handlers = [
  // ---- Auth ----
  http.post('http://localhost:8000/api/v1/auth/register', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string }
    if (!body.email || !body.password) {
      return HttpResponse.json(
        { error: { code: 'auth.email_invalid', message: 'Invalid email', request_id: 'mock' } },
        { status: 422 },
      )
    }
    if (body.email === 'taken@intercraft.io') {
      return HttpResponse.json(
        { error: { code: 'auth.email_taken', message: 'Email already registered', request_id: 'mock' } },
        { status: 409 },
      )
    }
    return HttpResponse.json({ user: { ...MOCK_USER, email: body.email }, tokens: TOKENS })
  }),

  http.post('http://localhost:8000/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string }
    if (body.email !== 'demo@intercraft.io' || body.password !== 'Demo1234') {
      return HttpResponse.json(
        { error: { code: 'auth.invalid_credentials', message: 'Invalid email or password', request_id: 'mock' } },
        { status: 401 },
      )
    }
    return HttpResponse.json({ user: MOCK_USER, tokens: TOKENS, evicted_session_id: null })
  }),

  http.post('http://localhost:8000/api/v1/auth/refresh', () =>
    HttpResponse.json({ tokens: TOKENS }),
  ),
  http.post('http://localhost:8000/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),

  // ---- Users ----
  http.get('http://localhost:8000/api/v1/users/me', () => HttpResponse.json(MOCK_USER)),
  http.patch('http://localhost:8000/api/v1/users/me', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json({ ...MOCK_USER, ...body, updated_at: new Date().toISOString() })
  }),

  // ---- Sessions ----
  http.get('http://localhost:8000/api/v1/users/me/sessions', () =>
    HttpResponse.json([
      {
        id: 'sess-1',
        device_id: 'dev-1',
        device_name: 'Chrome',
        ip: '127.0.0.1',
        user_agent: 'jest',
        created_at: '2026-06-01T00:00:00Z',
        last_seen_at: '2026-06-12T00:00:00Z',
        is_current: true,
      },
    ]),
  ),
  http.delete('http://localhost:8000/api/v1/users/me/sessions/:id', () => new HttpResponse(null, { status: 204 })),

  // ---- Resume branches ----
  http.get('http://localhost:8000/api/v1/resume-branches', () => HttpResponse.json(BRANCHES)),
  http.get('http://localhost:8000/api/v1/resume-branches/:id', ({ params }) => {
    const b = BRANCHES.find((x) => x.id === params.id)
    if (!b) return HttpResponse.json({ error: { code: 'resource.not_found' } }, { status: 404 })
    return HttpResponse.json(b)
  }),
  http.post('http://localhost:8000/api/v1/resume-branches', async ({ request }) => {
    const body = (await request.json()) as { name: string }
    return HttpResponse.json({
      branch: {
        id: `branch-${Date.now()}`,
        user_id: MOCK_USER.id,
        parent_id: null,
        name: body.name,
        is_main: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        last_edited_at: null,
      },
    })
  }),
  http.delete('http://localhost:8000/api/v1/resume-branches/:id', () => new HttpResponse(null, { status: 204 })),
  http.post('http://localhost:8000/api/v1/resume-branches/:id/refresh-from-parent', ({ params }) => {
    const b = BRANCHES.find((x) => x.id === params.id)
    return HttpResponse.json({ branch: b, added: 0, updated: 0, removed: 0 })
  }),

  // ---- Resume blocks ----
  http.get('http://localhost:8000/api/v1/resume-branches/:id/blocks', () => HttpResponse.json(BLOCKS)),
  http.post('http://localhost:8000/api/v1/resume-branches/:id/blocks', async ({ request }) => {
    const body = (await request.json()) as { type: string; title?: string; content_md?: string }
    return HttpResponse.json({
      id: `block-${Date.now()}`,
      branch_id: '01900000-0000-7000-8000-000000000m01',
      type: body.type,
      title: body.title ?? null,
      content_md: body.content_md ?? '',
      order_index: `a${Date.now()}`,
      meta: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
  }),
  http.patch('http://localhost:8000/api/v1/resume-blocks/:id', async ({ request, params }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json({ ...BLOCKS[0], id: params.id, ...body, updated_at: new Date().toISOString() })
  }),
  http.patch('http://localhost:8000/api/v1/resume-blocks/:id/reorder', ({ params }) =>
    HttpResponse.json({ ...BLOCKS[0], id: params.id, order_index: `a${Date.now()}` }),
  ),
  http.delete('http://localhost:8000/api/v1/resume-blocks/:id', () => new HttpResponse(null, { status: 204 })),

  // ---- Versions ----
  http.get('http://localhost:8000/api/v1/resume-branches/:id/versions', () =>
    HttpResponse.json([
      {
        id: 'v-1',
        branch_id: BRANCHES[0].id,
        version_no: 1,
        label: '初始化',
        trigger: 'manual',
        is_full_snapshot: true,
        block_count: 1,
        created_at: '2026-06-01T00:00:00Z',
      },
    ]),
  ),
  http.post('http://localhost:8000/api/v1/resume-branches/:id/versions', async ({ request }) => {
    const body = (await request.json()) as { label: string }
    return HttpResponse.json({
      id: 'v-2',
      branch_id: BRANCHES[0].id,
      version_no: 2,
      label: body.label,
      trigger: 'manual',
      is_full_snapshot: true,
      block_count: 1,
      created_at: new Date().toISOString(),
    })
  }),
  http.post('http://localhost:8000/api/v1/resume-branches/:id/versions/:no/rollback', () =>
    HttpResponse.json({
      new_branch: { ...BRANCHES[0], id: 'rollback-branch', name: '回滚 v1' },
      restored_version_no: 1,
    }),
  ),

  // ---- 019 — Jobs (cross-module linking) ----
  http.get('http://localhost:8000/api/v1/jobs', () =>
    HttpResponse.json({
      data: [
        {
          id: 'job-mock-1',
          user_id: MOCK_USER.id,
          company: '字节',
          position: '高级前端',
          jd_url: null,
          branch_id: null,
          status: 'applied',
          status_history: [],
          note: null,
          base_location: '北京',
          requirements_md:
            '## 岗位要求\n- 3年以上 React 经验\n- 熟悉可视化与 canvas 渲染\n- 有大型项目性能优化经验\n- 良好的工程化与团队协作能力',
          employment_type: 'experienced',
          salary_range_text: '30-50K',
          headcount: 5,
          created_at: '2026-06-17T00:00:00Z',
          updated_at: '2026-06-17T00:00:00Z',
        },
      ],
      next_cursor: null,
      has_more: false,
    }),
  ),
  http.get('http://localhost:8000/api/v1/jobs/:id', ({ params }) =>
    HttpResponse.json({
      id: params.id,
      user_id: MOCK_USER.id,
      company: '字节',
      position: '高级前端',
      jd_url: null,
      branch_id: null,
      status: 'applied',
      status_history: [],
      note: null,
      base_location: '北京',
      requirements_md:
        '## 岗位要求\n- 3年以上 React 经验\n- 熟悉可视化与 canvas 渲染\n- 有大型项目性能优化经验\n- 良好的工程化与团队协作能力',
      employment_type: 'experienced',
      salary_range_text: '30-50K',
      headcount: 5,
      created_at: '2026-06-17T00:00:00Z',
      updated_at: '2026-06-17T00:00:00Z',
    }),
  ),
  http.patch('http://localhost:8000/api/v1/jobs/:id', async ({ request, params }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json({
      id: params.id,
      user_id: MOCK_USER.id,
      company: '字节',
      position: '高级前端',
      jd_url: null,
      branch_id: body.branch_id ?? null,
      status: 'applied',
      status_history: [],
      note: null,
      base_location: '北京',
      requirements_md: null,
      employment_type: 'experienced',
      salary_range_text: null,
      headcount: null,
      created_at: '2026-06-17T00:00:00Z',
      updated_at: '2026-06-17T00:00:00Z',
    })
  }),

  // ---- 019 — Interview sessions (cross-module linking, US3) ----
  http.post('http://localhost:8000/api/v1/interview-sessions', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json({
      data: {
        ...SESSION_BODY,
        id: `mock-session-${Date.now()}`,
        branch_id: body.branch_id ?? null,
        position: body.position ?? null,
        company: body.company ?? null,
        mode: body.mode ?? 'text',
        job_id: body.job_id ?? null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    })
  }),
  http.get('http://localhost:8000/api/v1/interview-sessions/:id', () =>
    HttpResponse.json({ data: { ...SESSION_BODY, id: 'sess-stub' } }),
  ),
  http.get('http://localhost:8000/api/v1/interview-sessions', () =>
    HttpResponse.json({ data: [], next_cursor: null, has_more: false }),
  ),
  http.post('http://localhost:8000/api/v1/interview-sessions/:id/start', () =>
    HttpResponse.json({
      data: { id: 'sess-stub', status: 'running', started_at: new Date().toISOString() },
    }),
  ),
  http.post('http://localhost:8000/api/v1/interview-sessions/:id/answers', () =>
    HttpResponse.json({ data: { accepted: true } }),
  ),
  http.get('http://localhost:8000/api/v1/interview-sessions/:id/resume', () =>
    HttpResponse.json({
      data: {
        thread_id: 'thread-stub',
        values: { messages: [], questions: [], scores: [] },
      },
    }),
  ),
  http.delete('http://localhost:8000/api/v1/interview-sessions/:id', () =>
    new HttpResponse(null, { status: 204 }),
  ),
]

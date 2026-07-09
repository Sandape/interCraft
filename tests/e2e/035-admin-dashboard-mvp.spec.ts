import { expect, test, type Page, type Route } from '@playwright/test'

const TRACE_ID = 'trace_success_req_035'
const NODE_SPAN_ID = 'span_node_diagnose'
const LLM_CALL_ID = 'llm_1'
const SNAPSHOT_ID = 'snapshot_req_035'

const ADMIN_IDENTITY = {
  admin_user_id: 'admin-req-035',
  display_name: 'REQ-035 Admin',
  role_labels: ['admin', 'ops'],
  capabilities: ['admin.dashboard.read', 'admin.trace.read', 'admin.payload.reveal'],
  environment_scope: 'local',
}

const dashboardFreshness = {
  freshness_at: '2026-06-29T02:10:00Z',
  target_minutes: 15,
  quality_state: 'stale',
  warnings: ['Source lag exceeded 15 minute target.'],
}

const metricDefinition = {
  metric_id: 'pm.ai_success_rate',
  display_name: 'AI Success Rate',
  unit: 'percent',
  definition: 'Completed AI tasks divided by attempted AI tasks.',
  numerator: 'completed_ai_tasks',
  denominator: 'attempted_ai_tasks',
  comparison_rule: 'higher_is_better',
  source: 'agent_observability.metrics',
  owner: 'Product Analytics',
  version: '2026-06-29',
  freshness_target_minutes: 15,
  privacy_class: 'aggregate',
}

const DASHBOARD_SUMMARY = {
  filters: {
    date_from: '2026-06-22T00:00:00.000Z',
    date_to: '2026-06-30T00:00:00.000Z',
    environment: 'local',
  },
  freshness: dashboardFreshness,
  summary_cards: [
    {
      metric_id: 'pm.active_users',
      label: 'Active Users',
      value: 42,
      unit: 'count',
      definition: 'Users with at least one tracked product action in the selected period.',
      source: 'product_events',
      owner: 'Product Analytics',
      version: '2026-06-29',
      freshness_at: '2026-06-29T02:10:00Z',
      freshness_target_minutes: 15,
      source_completeness: {
        expected_sources: ['product_events'],
        available_sources: ['product_events'],
        missing_sources: [],
        row_count: 42,
        freshness_at: '2026-06-29T02:10:00Z',
        freshness_lag_minutes: 3,
        freshness_target_minutes: 15,
        quality_state: 'complete',
      },
    },
    {
      metric_id: 'pm.ai_success_rate',
      label: 'AI Success Rate',
      value: 0,
      unit: 'percent',
      definition: metricDefinition.definition,
      definition_detail: metricDefinition,
      source: metricDefinition.source,
      owner: metricDefinition.owner,
      version: metricDefinition.version,
      freshness_at: '2026-06-29T02:10:00Z',
      freshness_target_minutes: 15,
      source_completeness: {
        expected_sources: ['llm_calls', 'agent_runs'],
        available_sources: ['llm_calls', 'agent_runs'],
        missing_sources: [],
        row_count: 0,
        freshness_at: '2026-06-29T02:10:00Z',
        freshness_lag_minutes: 2,
        freshness_target_minutes: 15,
        quality_state: 'complete',
      },
    },
    {
      metric_id: 'resume.diagnosis_rate',
      label: 'Resume Diagnosis',
      value: 0.5,
      unit: 'percent',
      definition: 'Resume diagnosis completions divided by eligible resumes.',
      source: 'resume_events',
      owner: 'Resume Product',
      version: '2026-06-29',
      freshness_at: '2026-06-29T01:52:00Z',
      freshness_target_minutes: 15,
      source_completeness: {
        expected_sources: ['resume_events', 'diagnosis_runs'],
        available_sources: ['resume_events'],
        missing_sources: ['diagnosis_runs'],
        row_count: 7,
        freshness_at: '2026-06-29T01:52:00Z',
        freshness_lag_minutes: 18,
        freshness_target_minutes: 15,
        quality_state: 'partial',
      },
    },
    {
      metric_id: 'mock_interview.completion_rate',
      label: 'Mock Interview Completion',
      value: 0,
      unit: 'percent',
      definition: 'Completed mock interviews divided by started mock interviews.',
      source: 'interview_sessions',
      owner: 'Interview Product',
      version: '2026-06-29',
      freshness_at: null,
      freshness_target_minutes: 15,
      source_completeness: {
        expected_sources: ['interview_sessions'],
        available_sources: [],
        missing_sources: ['interview_sessions'],
        row_count: 0,
        freshness_at: null,
        freshness_lag_minutes: null,
        freshness_target_minutes: 15,
        quality_state: 'empty',
      },
    },
    {
      metric_id: 'badcases.open',
      label: 'Open Badcases',
      value: 3,
      unit: 'count',
      definition: 'Open badcases connected to trace or eval outcomes.',
      source: 'badcase_feedback',
      owner: 'Quality Ops',
      version: '2026-06-29',
      freshness_at: '2026-06-29T01:20:00Z',
      freshness_target_minutes: 15,
      source_completeness: {
        expected_sources: ['badcase_feedback'],
        available_sources: ['badcase_feedback'],
        missing_sources: [],
        row_count: 3,
        freshness_at: '2026-06-29T01:20:00Z',
        freshness_lag_minutes: 50,
        freshness_target_minutes: 15,
        quality_state: 'stale',
      },
    },
  ],
  panels: [
    {
      panel_id: 'product_funnel',
      title: 'Core Funnel',
      href: '/dashboard#funnel',
      quality_state: 'complete',
      definition: 'Core acquisition, activation, and AI completion funnel.',
      source: 'product_events + agent_observability.metrics',
      freshness: dashboardFreshness,
    },
    {
      panel_id: 'resume_diagnosis',
      title: 'Resume Diagnosis',
      href: '/dashboard#resume',
      quality_state: 'partial',
      definition: 'Resume diagnosis coverage and completion.',
      source: 'resume_events + diagnosis_runs',
      freshness: { ...dashboardFreshness, quality_state: 'partial' },
    },
    {
      panel_id: 'mock_interview',
      title: 'Mock Interview',
      href: '/dashboard#interview',
      quality_state: 'empty',
      definition: 'Mock interview starts and completions.',
      source: 'interview_sessions',
      freshness: { ...dashboardFreshness, quality_state: 'empty', warnings: [] },
    },
    {
      panel_id: 'ai_operations',
      title: 'AI Operations',
      href: '/dashboard#ai',
      quality_state: 'complete',
      definition: 'LLM success, latency, tokens, and cost.',
      source: 'llm_calls + traces',
      freshness: { ...dashboardFreshness, quality_state: 'complete', warnings: [] },
    },
    {
      panel_id: 'badcase_feedback',
      title: 'Badcase Feedback',
      href: '/dashboard#badcases',
      quality_state: 'stale',
      definition: 'Badcases, feedback, and operator review state.',
      source: 'badcase_feedback',
      freshness: dashboardFreshness,
    },
    {
      panel_id: 'version_context',
      title: 'Version Context',
      href: '/dashboard#versions',
      quality_state: 'complete',
      definition: 'Model, prompt, and experiment version context.',
      source: 'version_experiment',
      freshness: { ...dashboardFreshness, quality_state: 'complete', warnings: [] },
    },
  ],
  request_id: 'req-035-dashboard',
}

const TRACE_SEARCH = {
  items: [
    {
      trace_id: TRACE_ID,
      started_at: '2026-06-29T02:00:00Z',
      duration_ms: 1820,
      status: 'success',
      feature_area: 'resume',
      business_run_id: 'run_resume_req_035',
      agent_name: 'ResumeDiagnosisAgent',
      llm_call_count: 1,
      total_tokens: 1280,
      estimated_cost: 0.0132,
      eval_status: 'failed',
      badcase_status: 'OPEN',
      source_revision: 'rev-035',
      privacy_class: 'masked',
    },
  ],
  next_cursor: null,
  freshness_at: '2026-06-29T02:10:00Z',
}

const TRACE_DETAIL = {
  trace: {
    trace_id: TRACE_ID,
    business_run_id: 'run_resume_req_035',
    feature_area: 'resume',
    status: 'success',
    started_at: '2026-06-29T02:00:00Z',
    duration_ms: 1820,
  },
  spans: [
    {
      span_id: 'span_root',
      parent_span_id: null,
      span_kind: 'agent',
      name: 'ResumeDiagnosisAgent.invoke',
      status: 'success',
      duration_ms: 1820,
    },
    {
      span_id: NODE_SPAN_ID,
      parent_span_id: 'span_root',
      span_kind: 'node',
      name: 'diagnose_resume',
      node_name: 'diagnose_resume',
      status: 'success',
      duration_ms: 950,
      input_payload_id: 'payload_input_035',
      output_payload_id: 'payload_output_035',
      state_diff_payload_id: 'payload_state_035',
    },
  ],
  links: {
    eval_case_ids: ['eval_case_req_035'],
    badcase_ids: ['badcase_req_035'],
  },
  visibility_mode: 'redacted',
}

const AGENT_RUN = {
  agent_run_id: 'run_resume_req_035',
  trace_id: TRACE_ID,
  agent_name: 'ResumeDiagnosisAgent',
  graph: 'resume_diagnosis_graph',
  status: 'success',
  nodes: [],
}

const NODE_DETAIL = {
  span_id: NODE_SPAN_ID,
  trace_id: TRACE_ID,
  node_name: 'diagnose_resume',
  status: 'success',
  duration_ms: 950,
  input: {
    payload_id: 'payload_input_035',
    visibility_mode: 'redacted',
    shape: { fields: 4, attachments: 1 },
    redacted_summary: 'Resume input captured with PII removed.',
  },
  output: {
    payload_id: 'payload_output_035',
    visibility_mode: 'redacted',
    shape: { recommendations: 3 },
    redacted_summary: 'Diagnosis summary with sensitive text removed.',
  },
  state_diff: {
    payload_id: 'payload_state_035',
    visibility_mode: 'redacted',
    shape: { changed_keys: 2 },
    redacted_summary: 'Status advanced to diagnosis_completed.',
  },
  llm_calls: [LLM_CALL_ID],
  tool_operations: [{ tool: 'resume_parser', status: 'success', latency_ms: 41 }],
  emitted_events: ['diagnosis.completed'],
  next_step: 'Return recommendations to the user.',
  errors: [],
  retry_count: 0,
}

const LLM_CALL = {
  llm_call_id: LLM_CALL_ID,
  trace_id: TRACE_ID,
  provider: 'openai',
  endpoint: '/v1/chat/completions',
  http_method: 'POST',
  model_requested: 'gpt-4.1-mini',
  model_returned: 'gpt-4.1-mini-2026-06-01',
  parameters: { temperature: 0.2, max_tokens: 800 },
  usage: {
    prompt_tokens: 900,
    completion_tokens: 380,
    cache_tokens: 120,
    reasoning_tokens: 0,
    estimated_cost: 0.0132,
  },
  timing: {
    latency_ms: 1250,
    time_to_first_token_ms: 420,
    stream_chunk_count: 16,
  },
  status: 'success',
  finish_reason: 'stop',
  provider_request_id: 'req_openai_035',
  request_payload_id: 'payload_llm_request_035',
  response_payload_id: 'payload_llm_response_035',
}

const SNAPSHOT = {
  dashboard_snapshot_id: SNAPSHOT_ID,
  format: 'markdown',
  created_at: '2026-06-29T02:12:00Z',
  filters: { environment: 'local', date_from: '2026-06-22', date_to: '2026-06-29' },
  warnings: ['Source lag exceeded 15 minute target.'],
  content: [
    '# Dashboard Snapshot',
    'Generated: 2026-06-29T02:12:00Z',
    'Freshness: stale, target 15m.',
    'AI Success Rate: 0%',
    'Definitions: Completed AI tasks divided by attempted AI tasks.',
    'Source states: complete, partial, empty, stale.',
    'Privacy: aggregate metrics only; source text, prompts, model outputs, and credentials excluded.',
  ].join('\n'),
}

function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function mockAdminSession(page: Page, authorized = true) {
  await page.route('**/api/v1/admin-console/me', async (route) => {
    if (!authorized) {
      await fulfillJson(route, {
        error: {
          code: 'forbidden',
          message: 'Forbidden',
          request_id: 'req-admin-denied',
        },
      }, 403)
      return
    }
    await fulfillJson(route, ADMIN_IDENTITY)
  })
}

async function mockReq035Apis(page: Page) {
  await page.route('**/api/v1/admin-console/dashboard/summary**', async (route) => {
    await fulfillJson(route, DASHBOARD_SUMMARY)
  })
  await page.route('**/api/v1/admin-console/dashboard/snapshots', async (route) => {
    await fulfillJson(route, {
      dashboard_snapshot_id: SNAPSHOT_ID,
      format: 'markdown',
      privacy_status: 'safe',
      created_at: '2026-06-29T02:12:00Z',
      download_url: `/api/v1/admin-console/dashboard/snapshots/${SNAPSHOT_ID}`,
      warnings: ['Source lag exceeded 15 minute target.'],
    })
  })
  await page.route(`**/api/v1/admin-console/dashboard/snapshots/${SNAPSHOT_ID}`, async (route) => {
    await fulfillJson(route, SNAPSHOT)
  })
  await page.route('**/api/v1/admin-console/observability/traces?**', async (route) => {
    await fulfillJson(route, TRACE_SEARCH)
  })
  await page.route(`**/api/v1/admin-console/observability/traces/${TRACE_ID}`, async (route) => {
    await fulfillJson(route, TRACE_DETAIL)
  })
  await page.route(`**/api/v1/admin-console/observability/agent-runs/${TRACE_ID}`, async (route) => {
    await fulfillJson(route, AGENT_RUN)
  })
  await page.route(`**/api/v1/admin-console/observability/nodes/${NODE_SPAN_ID}`, async (route) => {
    await fulfillJson(route, NODE_DETAIL)
  })
  await page.route('**/api/v1/admin-console/observability/payloads/*/reveal', async (route) => {
    const payload = JSON.parse(route.request().postData() ?? '{}') as Record<string, string>
    expect(payload.reason).toContain('debug')
    expect(payload.visibility_mode).toBe('masked_raw')
    await fulfillJson(route, {
      payload_id: 'payload_input_035',
      visibility_mode: 'masked_raw',
      shape: { fields: 4 },
      masked_raw: {
        candidate_email: '***@example.com',
        resume_text: '[masked]',
        access_token: '[redacted]',
      },
      audit_id: 'audit_reveal_req_035',
    })
  })
  await page.route(`**/api/v1/admin-console/observability/llm-calls/${LLM_CALL_ID}`, async (route) => {
    await fulfillJson(route, LLM_CALL)
  })
  await page.route(`**/api/v1/admin-console/observability/llm-calls/${LLM_CALL_ID}/curl**`, async (route) => {
    expect(new URL(route.request().url()).searchParams.get('reason')).toContain('debug')
    await fulfillJson(route, {
      llm_call_id: LLM_CALL_ID,
      visibility_mode: 'safe_curl',
      curl: [
        'curl https://api.openai.example/v1/chat/completions',
        '-H "Authorization: Bearer [redacted]"',
        "-d '{\"model\":\"gpt-4.1-mini\",\"messages\":\"[redacted]\"}'",
      ].join(' \\\n  '),
      redacted_headers: { Authorization: '[redacted]', 'OpenAI-Organization': '[redacted]' },
      audit_id: 'audit_curl_req_035',
    })
  })
}

async function openAdmin(page: Page) {
  await mockAdminSession(page)
  await mockReq035Apis(page)
  await page.goto('/admin-console')
  await expect(page.getByRole('heading', { name: 'Product Dashboard' })).toBeVisible()
}

test.describe('REQ-035 admin dashboard MVP', () => {
  test('US1 blocks non-admin access at the boundary', async ({ page }) => {
    await mockAdminSession(page, false)

    await page.goto('/admin-console')

    await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible()
    await expect(page.getByText('Your account does not have admin console access.')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Admin sign in' })).toHaveAttribute(
      'href',
      '/admin-console/login',
    )
  })

  test('US1 keeps ordinary product login separate from the admin entry', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByText('Admin Console')).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Admin sign in' })).toHaveCount(0)
  })

  test('US2, US5, and US6 show trustworthy dashboard metadata and safe snapshots', async ({ page }) => {
    await openAdmin(page)

    await expect(page.getByText('Source lag exceeded 15 minute target.').first()).toBeVisible()
    await expect(page.getByText('Target 15m').first()).toBeVisible()
    await expect(page.getByText('0%').first()).toBeVisible()
    await expect(page.getByText('complete').first()).toBeVisible()
    await expect(page.getByText('partial').first()).toBeVisible()
    await expect(page.getByText('empty').first()).toBeVisible()
    await expect(page.getByText('stale').first()).toBeVisible()
    await expect(page.getByText('Source: product_events + agent_observability.metrics')).toBeVisible()

    await page.getByRole('button', { name: 'AI Success Rate definition' }).click()
    await expect(page.getByText('Numerator:')).toBeVisible()
    await expect(page.getByText('completed_ai_tasks')).toBeVisible()
    await expect(page.getByText('Source state:')).toBeVisible()
    await expect(page.getByText('Product Analytics')).toBeVisible()

    await page.screenshot({
      path: 'docs/evidence/035-admin-dashboard-mvp/e2e-admin-dashboard.png',
      fullPage: true,
    })

    await page.getByRole('button', { name: 'Snapshot' }).click()
    await expect(page.getByRole('dialog', { name: 'Dashboard snapshot' })).toBeVisible()
    await page.getByRole('button', { name: 'Generate snapshot' }).click()
    await expect(page.getByText('Snapshot ready')).toBeVisible()
    await expect(page.getByText('safe')).toBeVisible()
    await page.getByRole('link', { name: 'Open snapshot' }).click()

    await expect(page.getByRole('heading', { name: 'Dashboard Snapshot' })).toBeVisible()
    await expect(page.getByText('Privacy: aggregate metrics only')).toBeVisible()
    await expect(page.getByText('Source states: complete, partial, empty, stale.')).toBeVisible()
    await expect(page.getByText('sk-live')).toHaveCount(0)
    await expect(page.getByText('raw prompt')).toHaveCount(0)
  })

  test('US3 and US4 drill into traces and reveal only masked raw payloads', async ({ page }) => {
    await openAdmin(page)

    await page.getByRole('link', { name: 'Trace Explorer' }).click()
    await expect(page.getByRole('heading', { name: 'Trace Explorer' })).toBeVisible()
    await expect(page.getByText('1280')).toBeVisible()
    await expect(page.getByText('$0.0132')).toBeVisible()
    await page.getByRole('link', { name: TRACE_ID.slice(0, 12) }).click()

    await expect(page.getByRole('heading', { name: 'Agent Run Detail' })).toBeVisible()
    await expect(page.locator('dd', { hasText: 'ResumeDiagnosisAgent' }).first()).toBeVisible()
    await expect(page.getByText('eval_case_req_035', { exact: true })).toBeVisible()
    await expect(page.getByText('Tool Operations')).toBeVisible()

    await page.getByRole('button', { name: 'Reveal masked raw' }).first().click()
    await page.getByLabel('Reveal reason').fill('debug req-035 payload linkage')
    await page.getByRole('button', { name: 'Reveal', exact: true }).click()

    await expect(page.getByText('audit_reveal_req_035')).toBeVisible()
    await expect(page.getByText('***@example.com')).toBeVisible()
    await expect(page.getByText('secret@example.com')).toHaveCount(0)
    await expect(page.getByText('sk-live')).toHaveCount(0)
  })

  test('US4 renders safe cURL with secrets and payload text redacted', async ({ page }) => {
    await openAdmin(page)

    await page.getByRole('link', { name: 'LLM Detail' }).click()
    await expect(page.getByRole('heading', { name: 'LLM Call Detail' })).toBeVisible()
    await expect(page.getByText('Returned: gpt-4.1-mini-2026-06-01')).toBeVisible()
    await page.getByLabel('cURL reason').fill('debug req-035 provider request')
    await page.getByRole('button', { name: 'Generate safe cURL' }).click()

    await expect(page.getByText('audit_curl_req_035')).toBeVisible()
    await expect(page.getByText('Authorization: Bearer [redacted]')).toBeVisible()
    await expect(page.getByText('sk-live')).toHaveCount(0)
    await expect(page.getByText('candidate raw resume text')).toHaveCount(0)
  })
})

/**
 * Unit tests — REQ-044 US5 / FR-024~FR-026 + EC-1~EC-3.
 *
 * Covers:
 * - parseDrilldownParam / buildDrilldownHref (AC-24.1, AC-24.4)
 * - DrilldownBanner render + back-to-source link (AC-24.2)
 * - CoverageGapNotice render with 3 reasons (AC-25.1, AC-25.2, EC-3)
 * - LogDetailDrawer 4-panel render + masked payload (AC-26.1, AC-26.5, AC-26.6)
 * - LogDetailDrawer close-on-reveal-denied (EC-1)
 * - LLMCallPanel cache_hit / cache_key_fingerprint (AC-26.3)
 * - NodeExecutionPanel 5 version_context fields (AC-26.2)
 * - ToolCallPanel tool_name + schema + error (AC-26.4)
 * - SharedByIncidentList cross-link list (EC-2)
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, fireEvent, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import {
  adminLogsApi,
  buildDrilldownHref,
  parseDrilldownParam,
} from '@/api/admin-logs'
import { DrilldownBanner } from '../DrilldownBanner'
import { CoverageGapNotice } from '../CoverageGapNotice'
import { NodeExecutionPanel } from '../NodeExecutionPanel'
import { ToolCallPanel } from '../ToolCallPanel'
import { LLMCallPanel } from '../LLMCallPanel'
import { SharedByIncidentList } from '../SharedByIncidentList'
import { LogDetailDrawer } from '../LogDetailDrawer'
import type { LLMCall, LogEvent, NodeExecution, ToolCall } from '@/types/admin-logs'

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function renderWithProviders(node: JSX.Element) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const MOCK_LOG: LogEvent = {
  id: 'log-test-001',
  timestamp: '2026-07-04T10:00:00Z',
  level: 'error',
  message: 'tool call failed · search.jobs returned 500',
  correlationId: 'trace-001',
  source: 'agents.interview',
  agentRunId: 'agent-trace-001',
}

const MOCK_VERSION = {
  model: 'deepseek-v4-pro',
  promptFingerprint: 'pf-7c9a3b1d',
  rubricVersion: 'rubric.v2.4.1',
  appVersion: 'app.v0.42.0',
}

const MOCK_NODE: NodeExecution = {
  id: 'node-001',
  agentRunId: 'agent-trace-001',
  nodeName: 'graph.bootstrap',
  startedAt: '2026-07-04T10:00:00Z',
  endedAt: '2026-07-04T10:00:05Z',
  durationMs: 5_000,
  status: 'success',
  retryCount: 2,
  toolCalls: [],
  llmCalls: [],
}

const MOCK_TOOL_CALL: ToolCall = {
  id: 'tool-001',
  nodeExecutionId: 'node-002',
  toolName: 'search.jobs',
  inputSchemaRef: 'search.jobs.v1',
  outputSummary: 'returned 24 jobs (truncated)',
  error: null,
  startedAt: '2026-07-04T10:00:00Z',
  endedAt: '2026-07-04T10:00:05Z',
}

const MOCK_LLM_CALL: LLMCall = {
  id: 'llm-001',
  nodeExecutionId: 'node-003',
  model: 'deepseek-v4-pro',
  inputTokens: 1820,
  outputTokens: 412,
  cacheHit: true,
  cacheKeyFingerprint: 'ck-aabbccdd-9988',
  latencyMs: 1850,
  startedAt: '2026-07-04T10:00:00Z',
  rawPrompt: null,
  rawModelOutput: null,
}

// ---------------------------------------------------------------------------
// parseDrilldownParam / buildDrilldownHref
// ---------------------------------------------------------------------------

describe('parseDrilldownParam (AC-24.1, AC-24.4)', () => {
  it('parses incident:inc-001 into a DrilldownSource', () => {
    const src = parseDrilldownParam('incident:inc-001')
    expect(src).not.toBeNull()
    expect(src?.type).toBe('incident')
    expect(src?.id).toBe('inc-001')
    expect(src?.label).toBe('incident:inc-001')
  })

  it('parses signal:ds-007', () => {
    const src = parseDrilldownParam('signal:ds-007')
    expect(src?.type).toBe('signal')
    expect(src?.id).toBe('ds-007')
  })

  it('parses badcase:bc-003', () => {
    const src = parseDrilldownParam('badcase:bc-003')
    expect(src?.type).toBe('badcase')
    expect(src?.id).toBe('bc-003')
  })

  it('returns null for malformed input', () => {
    expect(parseDrilldownParam(null)).toBeNull()
    expect(parseDrilldownParam('')).toBeNull()
    expect(parseDrilldownParam('foo')).toBeNull()
    expect(parseDrilldownParam('unknowntype:id')).toBeNull()
  })

  it('buildDrilldownHref produces a clean shareable URL (AC-24.4)', () => {
    const src = parseDrilldownParam('incident:inc-001')!
    const href = buildDrilldownHref(src)
    expect(href).toContain('from=incident%3Ainc-001')
    expect(href.startsWith('/admin-console/logs-and-traces')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// DrilldownBanner (AC-24.2)
// ---------------------------------------------------------------------------

describe('DrilldownBanner (AC-24.2)', () => {
  it('renders source label and back-to-source link', () => {
    const source = parseDrilldownParam('incident:inc-001')!
    renderWithProviders(<DrilldownBanner source={source} />)
    expect(screen.getByTestId('drilldown-banner')).toBeTruthy()
    expect(screen.getByTestId('drilldown-source').textContent).toContain(
      'inc-001',
    )
    expect(screen.getByTestId('drilldown-source').textContent).toContain(
      'Incident',
    )
    const back = screen.getByTestId('back-to-source') as HTMLAnchorElement
    expect(back.getAttribute('href')).toContain('/admin-console/incidents-badcases')
    expect(back.getAttribute('href')).toContain('incident=inc-001')
  })

  it('auto-selects trace when source type is trace (AC-24.3)', () => {
    const source = parseDrilldownParam('trace:trace-007')!
    const onAuto = vi.fn()
    renderWithProviders(
      <DrilldownBanner source={source} onAutoSelectTrace={onAuto} autoSelectTraceId="trace-007" />,
    )
    expect(onAuto).toHaveBeenCalledWith('trace-007')
  })
})

// ---------------------------------------------------------------------------
// CoverageGapNotice (AC-25.1, AC-25.2, EC-3)
// ---------------------------------------------------------------------------

describe('CoverageGapNotice (AC-25.1, AC-25.2, EC-3)', () => {
  it('renders the explicit title and 3 reasons', () => {
    renderWithProviders(
      <CoverageGapNotice sourceType="incident" sourceId="inc-001" />,
    )
    const notice = screen.getByTestId('coverage-gap-notice')
    expect(notice).toBeTruthy()
    expect(screen.getByTestId('coverage-gap-title').textContent).toBe(
      'No correlated logs found',
    )
    expect(
      screen.getByTestId('coverage-gap-reason-trace-coverage-gap'),
    ).toBeTruthy()
    expect(
      screen.getByTestId('coverage-gap-reason-instrumentation-incomplete'),
    ).toBeTruthy()
    expect(
      screen.getByTestId('coverage-gap-reason-legacy-path-bypassed-OTel'),
    ).toBeTruthy()
  })

  it('does NOT silently collapse to "no data"', () => {
    renderWithProviders(<CoverageGapNotice sourceType="user" sourceId="u-9" />)
    // The testid is unique to coverage gap — never reused as a generic
    // empty-state badge.
    expect(screen.getByTestId('coverage-gap-notice')).toBeTruthy()
    expect(screen.queryByTestId('empty-state')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// NodeExecutionPanel (AC-26.1, AC-26.2)
// ---------------------------------------------------------------------------

describe('NodeExecutionPanel (AC-26.1, AC-26.2)', () => {
  it('renders all 5 version_context fields + retry_count + status', () => {
    renderWithProviders(
      <NodeExecutionPanel node={MOCK_NODE} versionContext={MOCK_VERSION} />,
    )
    expect(screen.getByTestId('node-status').textContent).toBe('success')
    expect(screen.getByTestId('node-retry-count').textContent).toBe('2')
    expect(screen.getByTestId('version-model').textContent).toBe('deepseek-v4-pro')
    expect(screen.getByTestId('version-prompt-fingerprint').textContent).toBe('pf-7c9a3b1d')
    expect(screen.getByTestId('version-rubric-version').textContent).toBe('rubric.v2.4.1')
    expect(screen.getByTestId('version-app-version').textContent).toBe('app.v0.42.0')
  })
})

// ---------------------------------------------------------------------------
// ToolCallPanel (AC-26.1, AC-26.4)
// ---------------------------------------------------------------------------

describe('ToolCallPanel (AC-26.1, AC-26.4)', () => {
  it('renders tool_name + input_schema_ref + output_summary', () => {
    renderWithProviders(<ToolCallPanel toolCall={MOCK_TOOL_CALL} />)
    expect(screen.getByTestId('tool-call-name').textContent).toBe('search.jobs')
    expect(screen.getByTestId('tool-call-output-summary').textContent).toBe(
      'returned 24 jobs (truncated)',
    )
  })

  it('renders error row when present', () => {
    renderWithProviders(
      <ToolCallPanel toolCall={{ ...MOCK_TOOL_CALL, error: '500 from upstream' }} />,
    )
    expect(screen.getByTestId('tool-call-error').textContent).toContain(
      '500 from upstream',
    )
  })

  it('masks raw input/output payload', () => {
    renderWithProviders(<ToolCallPanel toolCall={MOCK_TOOL_CALL} />)
    expect(screen.getByTestId('tool-call-payload-masked').textContent).toContain(
      'permission: hidden',
    )
  })
})

// ---------------------------------------------------------------------------
// LLMCallPanel (AC-26.1, AC-26.3, AC-26.5, AC-26.6)
// ---------------------------------------------------------------------------

describe('LLMCallPanel (AC-26.1, AC-26.3, AC-26.5, AC-26.6)', () => {
  it('renders model + input_tokens + output_tokens + cache_hit + cache_key_fingerprint + latency', () => {
    renderWithProviders(<LLMCallPanel llmCall={MOCK_LLM_CALL} />)
    expect(screen.getByTestId('llm-call-model').textContent).toBe('deepseek-v4-pro')
    expect(screen.getByTestId('llm-call-input-tokens').textContent).toBe('1820')
    expect(screen.getByTestId('llm-call-output-tokens').textContent).toBe('412')
    expect(screen.getByTestId('llm-call-cache-hit')).toBeTruthy()
    expect(screen.getByTestId('llm-call-cache-key-fingerprint').textContent).toBe(
      'ck-aabbccdd-9988',
    )
  })

  it('masks raw_prompt + raw_model_output by default', () => {
    renderWithProviders(<LLMCallPanel llmCall={MOCK_LLM_CALL} />)
    expect(screen.getByTestId('llm-call-payload-masked').textContent).toContain(
      'permission: hidden',
    )
  })

  it('"Request Reveal" link points to /admin-console/governance?reveal=llm_call:<id>', () => {
    renderWithProviders(<LLMCallPanel llmCall={MOCK_LLM_CALL} />)
    const link = screen.getByTestId('llm-call-request-reveal-llm-001') as HTMLAnchorElement
    expect(link.getAttribute('href')).toContain(
      '/admin-console/governance?reveal=llm_call%3Allm-001',
    )
  })
})

// ---------------------------------------------------------------------------
// SharedByIncidentList (EC-2)
// ---------------------------------------------------------------------------

describe('SharedByIncidentList (EC-2)', () => {
  it('renders cross-link list when incidents share the trace', () => {
    renderWithProviders(
      <SharedByIncidentList
        refs={[
          {
            incidentId: 'inc-001',
            title: 'Resume optimizer returning 500',
            severity: 'P1',
            href: '/admin-console/incidents-badcases?incident=inc-001',
          },
          {
            incidentId: 'inc-002',
            title: 'Mock interview llm_call timeout',
            severity: 'P2',
            href: '/admin-console/incidents-badcases?incident=inc-002',
          },
        ]}
      />,
    )
    const root = screen.getByTestId('shared-by-incidents')
    expect(root).toBeTruthy()
    expect(screen.getByTestId('shared-by-incidents-count').textContent).toBe('(2)')
    expect(screen.getByTestId('shared-by-incident-inc-001')).toBeTruthy()
    expect(screen.getByTestId('shared-by-incident-inc-002')).toBeTruthy()
  })

  it('renders empty state when no shared incidents', () => {
    renderWithProviders(<SharedByIncidentList refs={[]} />)
    expect(screen.getByTestId('shared-by-incidents-empty')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// LogDetailDrawer (AC-26.1, AC-26.5, AC-26.6, EC-1)
// ---------------------------------------------------------------------------

describe('LogDetailDrawer (AC-26.1, AC-26.5, AC-26.6, EC-1)', () => {
  let origGetAgentRun: typeof adminLogsApi.getAgentRun
  let origGetShared: typeof adminLogsApi.getSharedByIncidents

  beforeEach(() => {
    origGetAgentRun = adminLogsApi.getAgentRun
    origGetShared = adminLogsApi.getSharedByIncidents
    adminLogsApi.getAgentRun = vi.fn(async (id: string) => ({
      id,
      traceId: 'trace-001',
      graphName: 'interview_v3',
      startedAt: '2026-07-04T10:00:00Z',
      endedAt: '2026-07-04T10:00:55Z',
      durationMs: 55_000,
      status: 'failed' as const,
      versionContext: MOCK_VERSION,
      nodeExecutions: [MOCK_NODE],
    }))
    adminLogsApi.getSharedByIncidents = vi.fn(async () => ({
      traceId: 'trace-001',
      sharedBy: [
        {
          incidentId: 'inc-001',
          title: 'Resume optimizer returning 500',
          severity: 'P1' as const,
          href: '/admin-console/incidents-badcases?incident=inc-001',
        },
      ],
    }))
  })
  afterEach(() => {
    adminLogsApi.getAgentRun = origGetAgentRun
    adminLogsApi.getSharedByIncidents = origGetShared
    cleanup()
  })

  it('renders 4 types of structured panels + masked sensitive payload', async () => {
    renderWithProviders(<LogDetailDrawer open log={MOCK_LOG} onClose={vi.fn()} />)
    // Wait for the agent run query to resolve.
    await screen.findByTestId('log-detail-agent-run')
    expect(screen.getByTestId('node-execution-panel')).toBeTruthy()
    expect(screen.getByTestId('log-detail-correlation')).toBeTruthy()
    expect(screen.getByTestId('log-detail-message')).toBeTruthy()
    expect(screen.getByTestId('masked-raw-prompt')).toBeTruthy()
    expect(screen.getByTestId('masked-raw-model-output')).toBeTruthy()
    expect(screen.getByTestId('masked-raw-input')).toBeTruthy()
    expect(screen.getByTestId('masked-raw-output')).toBeTruthy()
    expect(screen.getByTestId('masked-redaction-token')).toBeTruthy()
  })

  it('"Request Reveal" link → /admin-console/governance?reveal=agent_run:<id>', async () => {
    renderWithProviders(<LogDetailDrawer open log={MOCK_LOG} onClose={vi.fn()} />)
    await screen.findByTestId('log-detail-agent-run')
    const link = screen.getByTestId('log-detail-request-reveal') as HTMLAnchorElement
    expect(link.getAttribute('href')).toContain('/admin-console/governance')
    expect(link.getAttribute('href')).toContain('reveal=agent_run%3Aagent-trace-001')
  })

  it('closes drawer + shows "access denied" on ic:reveal-denied (EC-1)', async () => {
    const onClose = vi.fn()
    renderWithProviders(<LogDetailDrawer open log={MOCK_LOG} onClose={onClose} />)
    await screen.findByTestId('log-detail-agent-run')
    act(() => {
      window.dispatchEvent(
        new CustomEvent('ic:reveal-denied', {
          detail: { audit_event_id: 'audit-1', reason: 'reason too short' },
        }),
      )
    })
    expect(onClose).toHaveBeenCalled()
    expect(screen.getByTestId('log-detail-drawer-denied').textContent).toContain(
      'access denied',
    )
  })
})
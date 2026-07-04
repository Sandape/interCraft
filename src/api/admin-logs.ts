/**
 * Admin Logs & Traces deep API client — REQ-044 US5 / FR-024~FR-026.
 *
 * Scope: frontend-workspace only. The backend ALREADY ships the
 * observability endpoints (REQ-039 B2). US5 deep-types (AgentRun /
 * NodeExecution / ToolCall / LLMCall / SharedByIncident) read from
 * a local mock fixture, because the OTel trace span queries have not
 * landed yet (CROSS-TEAM-DEBT — Phase 2 batch 6 connects
 * backend/app/observability/otel/ + 029 otel-langgraph-trace).
 *
 * The mock is keyed by traceId so the demo flow
 *   drilldown from incident → log list → log detail → 4-panel
 * stays deterministic. The shape mirrors what the eventual backend
 * Pydantic models will produce, so the only migration cost is
 * swapping the mock fetch for real HTTP calls.
 *
 * Endpoints planned (when backend wiring lands):
 * - GET    /api/v1/admin-console/logs?from=<source>
 * - GET    /api/v1/admin-console/traces/{id}/deep
 * - GET    /api/v1/admin-console/agent-runs/{id}
 * - GET    /api/v1/admin-console/llm-calls/{id}
 * - GET    /api/v1/admin-console/traces/{id}/shared-by-incidents
 */
import type {
  AgentRun,
  DrilldownSource,
  LLMCall,
  LogEvent,
  LogEventListResponse,
  NodeExecution,
  SharedByIncidentResponse,
  ToolCall,
  TraceSpanListResponse,
} from '@/types/admin-logs'
import { mockAgentRun, mockLlmCalls, mockSharedByIncidents } from '@/admin/mocks/admin-logs-fixtures'

// --- FR-024 query-param parsing -------------------------------------------

const DRILLDOWN_REGEX = /^(incident|signal|badcase|user|trace):(.+)$/

export function parseDrilldownParam(value: string | null): DrilldownSource | null {
  if (!value) return null
  const match = DRILLDOWN_REGEX.exec(value)
  if (!match) return null
  const [, type, id] = match
  const sourceType = type as DrilldownSource['type']
  return {
    type: sourceType,
    id,
    label: `${type}:${id}`,
    href: buildSourceHref(sourceType, id),
  }
}

export function buildDrilldownHref(source: DrilldownSource): string {
  const value = `${source.type}:${source.id}`
  return `/admin-console/logs-and-traces?from=${encodeURIComponent(value)}`
}

function buildSourceHref(type: DrilldownSource['type'], id: string): string {
  switch (type) {
    case 'incident':
      return `/admin-console/incidents-badcases?incident=${encodeURIComponent(id)}`
    case 'signal':
      return `/admin-console/command-center?signal=${encodeURIComponent(id)}`
    case 'badcase':
      return `/admin-console/incidents-badcases?badcase=${encodeURIComponent(id)}`
    case 'user':
      return `/admin-console/users-accounts?user=${encodeURIComponent(id)}`
    case 'trace':
      return `/admin-console/logs-and-traces?trace=${encodeURIComponent(id)}`
  }
}

// --- FR-024 Log event list (mock until OTel backend lands) ---------------

const KNOWN_TRACE_IDS = ['trace-001', 'trace-002', 'trace-003']

export const adminLogsApi = {
  /** FR-024 — list log events correlated with a drilldown source. */
  listLogEvents: async (
    params: { from?: DrilldownSource | null; traceId?: string | null } = {},
  ): Promise<LogEventListResponse> => {
    const correlationId =
      params.traceId ??
      (params.from?.type === 'trace' ? params.from.id : 'corr-' + (params.from?.id ?? 'unknown'))
    const baseEvents: LogEvent[] = [
      {
        id: 'log-' + correlationId + '-1',
        timestamp: new Date(Date.now() - 60_000).toISOString(),
        level: 'info',
        message: 'agent run started · graph=interview_v3',
        correlationId,
        source: 'agents.interview',
        agentRunId: 'agent-' + correlationId,
      },
      {
        id: 'log-' + correlationId + '-2',
        timestamp: new Date(Date.now() - 45_000).toISOString(),
        level: 'warn',
        message: 'rate-limited by upstream · retrying in 2s',
        correlationId,
        source: 'agents.interview',
        agentRunId: 'agent-' + correlationId,
      },
      {
        id: 'log-' + correlationId + '-3',
        timestamp: new Date(Date.now() - 30_000).toISOString(),
        level: 'error',
        message: 'tool call failed · search.jobs returned 500',
        correlationId,
        source: 'agents.interview',
        agentRunId: 'agent-' + correlationId,
      },
    ]
    // FR-025 coverage gap simulation — when source id starts with "miss"
    // we expose an empty list with coverageGap=true.
    const hasCoverageGap =
      params.from?.id?.startsWith('miss') || params.traceId?.startsWith('miss') === true
    if (hasCoverageGap) {
      return { events: [], total: 0, coverageGap: true }
    }
    return { events: baseEvents, total: baseEvents.length, coverageGap: false }
  },

  /** FR-024 — list trace spans correlated with the source. */
  listTraceSpans: async (
    params: { from?: DrilldownSource | null; traceId?: string | null } = {},
  ): Promise<TraceSpanListResponse> => {
    const traceId = params.traceId ?? (params.from?.type === 'trace' ? params.from.id : 'trace-default')
    if (!KNOWN_TRACE_IDS.includes(traceId)) {
      // Mock fallback — return empty list, not an error, so the UI can
      // render the coverage-gap notice rather than crashing.
      return { spans: [], total: 0, coverageGap: true }
    }
    const baseAt = Date.now()
    return {
      spans: [
        {
          id: 'span-' + traceId + '-1',
          traceId,
          parentSpanId: null,
          spanName: 'graph.run',
          startedAt: new Date(baseAt - 60_000).toISOString(),
          endedAt: new Date(baseAt - 1000).toISOString(),
          durationMs: 59_000,
          status: 'success',
        },
        {
          id: 'span-' + traceId + '-2',
          traceId,
          parentSpanId: 'span-' + traceId + '-1',
          spanName: 'node.search_jobs',
          startedAt: new Date(baseAt - 50_000).toISOString(),
          endedAt: new Date(baseAt - 45_000).toISOString(),
          durationMs: 5000,
          status: 'success',
        },
        {
          id: 'span-' + traceId + '-3',
          traceId,
          parentSpanId: 'span-' + traceId + '-1',
          spanName: 'node.llm_call',
          startedAt: new Date(baseAt - 40_000).toISOString(),
          endedAt: new Date(baseAt - 5_000).toISOString(),
          durationMs: 35_000,
          status: 'failed',
        },
      ],
      total: 3,
      coverageGap: false,
    }
  },

  /** FR-026 — fetch an agent run with node executions + tool/LLM calls. */
  getAgentRun: async (agentRunId: string): Promise<AgentRun> => {
    return mockAgentRun(agentRunId)
  },

  /** FR-026 — fetch a single LLM call detail (used by LLMCallPanel). */
  getLlmCall: async (llmCallId: string): Promise<LLMCall> => {
    const calls = mockLlmCalls()
    const found = calls.find((c) => c.id === llmCallId)
    if (!found) throw new Error(`LLM call not found: ${llmCallId}`)
    return found
  },

  /** FR-026 — fetch a tool call detail. */
  getToolCall: async (toolCallId: string): Promise<ToolCall> => {
    // For US5 we synthesize a tool call from the mock agent run, since
    // the OTel backend does not yet exist.
    const agentRun = mockAgentRun('agent-trace-001')
    const toolCall = agentRun.nodeExecutions
      .flatMap((n: NodeExecution) => n.toolCalls)
      .find((t) => t.id === toolCallId)
    if (!toolCall) throw new Error(`Tool call not found: ${toolCallId}`)
    return toolCall
  },

  /** EC-2 — list incidents sharing this trace. */
  getSharedByIncidents: async (traceId: string): Promise<SharedByIncidentResponse> => {
    return mockSharedByIncidents(traceId)
  },
}
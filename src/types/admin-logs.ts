/**
 * Admin Console Logs & Traces deep types — REQ-044 US5 / FR-024~FR-026.
 *
 * Mirrors backend REQ-039 observability + REQ-029 otel-langgraph-trace
 * schema (planned). For US5 (frontend-workspace scope) the shapes are
 * declared as trust-but-verify contracts that the frontend can mock
 * until the OTel module is wired in Phase 2 batch 6.
 *
 * [CROSS-TEAM-DEBT] Real OTel trace span queries land in Phase 2
 * batch 6 — connecting backend/app/observability/otel/ + 029
 * otel-langgraph-trace module. Until then this module is the source
 * of truth for the UI; types MUST stay in lockstep with the eventual
 * Pydantic models.
 */

// --- FR-024 Drilldown source ----------------------------------------------

export type DrilldownSourceType = 'incident' | 'signal' | 'badcase' | 'user' | 'trace'

export interface DrilldownSource {
  type: DrilldownSourceType
  id: string
  /** Human-readable label, e.g. "incident:inc-001". */
  label: string
  /** Absolute or relative URL to navigate back to the source detail. */
  href: string
}

// --- FR-026 Agent run / node execution / tool call / LLM call ------------

export type AgentRunStatus = 'success' | 'failed' | 'running' | 'pending'

export interface AgentRun {
  id: string
  traceId: string
  graphName: string
  startedAt: string
  endedAt: string | null
  durationMs: number | null
  status: AgentRunStatus
  /** Version context — required by FR-026 + FR-027 + spec US5 line 245. */
  versionContext: VersionContext
  /** Ordered list of node executions. */
  nodeExecutions: NodeExecution[]
}

export interface VersionContext {
  model: string
  promptFingerprint: string
  rubricVersion: string
  appVersion: string
}

export interface NodeExecution {
  id: string
  agentRunId: string
  nodeName: string
  startedAt: string
  endedAt: string | null
  durationMs: number | null
  status: AgentRunStatus
  retryCount: number
  /** Tool calls invoked from this node. */
  toolCalls: ToolCall[]
  /** LLM calls invoked from this node. */
  llmCalls: LLMCall[]
}

export interface ToolCall {
  id: string
  nodeExecutionId: string
  toolName: string
  /** Schema reference (e.g. "search.jobs.v1"). */
  inputSchemaRef: string
  /** Truncated summary — raw payload is masked per FR-026. */
  outputSummary: string
  error: string | null
  startedAt: string
  endedAt: string | null
}

export interface LLMCall {
  id: string
  nodeExecutionId: string
  model: string
  inputTokens: number
  outputTokens: number
  cacheHit: boolean
  /** Stable cache key fingerprint for FR-027 prompt caching. */
  cacheKeyFingerprint: string
  latencyMs: number
  startedAt: string
  /** Raw prompt — sensitive, masked by default per FR-026. */
  rawPrompt: string | null
  /** Raw model output — sensitive, masked by default per FR-026. */
  rawModelOutput: string | null
}

// --- FR-024 Log / trace list envelopes -------------------------------------

export interface LogEvent {
  id: string
  timestamp: string
  level: 'debug' | 'info' | 'warn' | 'error'
  message: string
  correlationId: string
  source: string
  /** Optional attached agent run id for FR-024 correlation. */
  agentRunId: string | null
}

export interface LogEventListResponse {
  events: LogEvent[]
  total: number
  /** True when no log rows exist but product event exists — FR-025. */
  coverageGap: boolean
}

export interface TraceSpan {
  id: string
  traceId: string
  parentSpanId: string | null
  spanName: string
  startedAt: string
  endedAt: string | null
  durationMs: number | null
  status: AgentRunStatus
}

export interface TraceSpanListResponse {
  spans: TraceSpan[]
  total: number
  coverageGap: boolean
}

// --- EC-2 Shared-by-incident ----------------------------------------------

export interface SharedByIncidentRef {
  incidentId: string
  title: string
  severity: 'P0' | 'P1' | 'P2' | 'P3'
  href: string
}

export interface SharedByIncidentResponse {
  traceId: string
  sharedBy: SharedByIncidentRef[]
}
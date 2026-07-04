/**
 * Admin Logs & Traces mock fixtures — REQ-044 US5 / FR-024~FR-026.
 *
 * Mock fixtures used by adminLogsApi until the real OTel-backed
 * endpoints land in Phase 2 batch 6 (CROSS-TEAM-DEBT).
 *
 * Deterministic so unit tests can pin specific ids and assert
 *   panel content without flakiness.
 */
import type {
  AgentRun,
  LLMCall,
  NodeExecution,
  SharedByIncidentResponse,
  ToolCall,
} from '@/types/admin-logs'

const AGENT_RUNS: Record<string, AgentRun> = {
  'agent-trace-001': {
    id: 'agent-trace-001',
    traceId: 'trace-001',
    graphName: 'interview_v3',
    startedAt: new Date(Date.now() - 60_000).toISOString(),
    endedAt: new Date(Date.now() - 5_000).toISOString(),
    durationMs: 55_000,
    status: 'failed',
    versionContext: {
      model: 'deepseek-v4-pro',
      promptFingerprint: 'pf-7c9a3b1d',
      rubricVersion: 'rubric.v2.4.1',
      appVersion: 'app.v0.42.0',
    },
    nodeExecutions: [
      {
        id: 'node-001',
        agentRunId: 'agent-trace-001',
        nodeName: 'graph.bootstrap',
        startedAt: new Date(Date.now() - 60_000).toISOString(),
        endedAt: new Date(Date.now() - 55_000).toISOString(),
        durationMs: 5_000,
        status: 'success',
        retryCount: 0,
        toolCalls: [],
        llmCalls: [],
      },
      {
        id: 'node-002',
        agentRunId: 'agent-trace-001',
        nodeName: 'node.search_jobs',
        startedAt: new Date(Date.now() - 55_000).toISOString(),
        endedAt: new Date(Date.now() - 50_000).toISOString(),
        durationMs: 5_000,
        status: 'success',
        retryCount: 1,
        toolCalls: [
          {
            id: 'tool-001',
            nodeExecutionId: 'node-002',
            toolName: 'search.jobs',
            inputSchemaRef: 'search.jobs.v1',
            outputSummary: 'returned 24 jobs (truncated)',
            error: null,
            startedAt: new Date(Date.now() - 55_000).toISOString(),
            endedAt: new Date(Date.now() - 50_000).toISOString(),
          },
        ],
        llmCalls: [],
      },
      {
        id: 'node-003',
        agentRunId: 'agent-trace-001',
        nodeName: 'node.llm_call',
        startedAt: new Date(Date.now() - 50_000).toISOString(),
        endedAt: new Date(Date.now() - 5_000).toISOString(),
        durationMs: 45_000,
        status: 'failed',
        retryCount: 2,
        toolCalls: [],
        llmCalls: [
          {
            id: 'llm-001',
            nodeExecutionId: 'node-003',
            model: 'deepseek-v4-pro',
            inputTokens: 1820,
            outputTokens: 412,
            cacheHit: true,
            cacheKeyFingerprint: 'ck-aabbccdd-9988',
            latencyMs: 1850,
            startedAt: new Date(Date.now() - 50_000).toISOString(),
            // Sensitive — masked by default per FR-026.
            rawPrompt: null,
            rawModelOutput: null,
          },
          {
            id: 'llm-002',
            nodeExecutionId: 'node-003',
            model: 'deepseek-v4-pro',
            inputTokens: 2200,
            outputTokens: 0,
            cacheHit: false,
            cacheKeyFingerprint: 'ck-ee112233-4455',
            latencyMs: 30_000,
            startedAt: new Date(Date.now() - 25_000).toISOString(),
            rawPrompt: null,
            rawModelOutput: null,
          },
        ],
      },
    ],
  },
}

const LLM_CALLS: LLMCall[] = AGENT_RUNS['agent-trace-001'].nodeExecutions.flatMap(
  (n: NodeExecution) => n.llmCalls,
)

const SHARED_BY_INCIDENTS: Record<string, SharedByIncidentResponse> = {
  'trace-001': {
    traceId: 'trace-001',
    sharedBy: [
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
    ],
  },
}

export function mockAgentRun(agentRunId: string): AgentRun {
  // Always return the canonical agent run, regardless of id, so the
  // panel renders deterministic content for the demo flow. If a
  // different id is passed, we synthesize a minimal stub so the UI
  // does not crash for ad-hoc ids in tests.
  if (AGENT_RUNS[agentRunId]) return AGENT_RUNS[agentRunId]
  return {
    id: agentRunId,
    traceId: 'trace-' + agentRunId,
    graphName: 'unknown',
    startedAt: new Date().toISOString(),
    endedAt: null,
    durationMs: null,
    status: 'running',
    versionContext: {
      model: 'unknown',
      promptFingerprint: 'unknown',
      rubricVersion: 'unknown',
      appVersion: 'unknown',
    },
    nodeExecutions: [],
  }
}

export function mockLlmCalls(): LLMCall[] {
  return LLM_CALLS
}

export function mockToolCalls(): ToolCall[] {
  return AGENT_RUNS['agent-trace-001'].nodeExecutions.flatMap((n: NodeExecution) => n.toolCalls)
}

export function mockSharedByIncidents(traceId: string): SharedByIncidentResponse {
  return SHARED_BY_INCIDENTS[traceId] ?? { traceId, sharedBy: [] }
}
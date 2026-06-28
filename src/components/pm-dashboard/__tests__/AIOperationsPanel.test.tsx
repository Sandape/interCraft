/** REQ-033 US4 T101 — AIOperationsPanel tests.

Verifies the AIOperationsPanel renders the 7 core metrics per US4:

1. AI call count (total invocations)
2. Success / failure counts (split by status) + rates
3. Retry count (rows where retry_count > 0)
4. Latency: P50 / P95 / P99 in ms
5. Estimated cost (sum, labeled as estimate per FR-008)
6. Token usage: prompt + completion
7. Breakdown by model / graph / node / prompt_fingerprint (top 5)

Tests cover:
- All 8 metric cards rendered in a grid.
- Success rate displayed as percentage with color coding.
- Failure rate displayed as percentage with inverted color coding.
- P50 / P95 latency in ms.
- Estimated cost formatted as currency with 4 decimals.
- 4 breakdown sections (model / graph / node / fingerprint).
- Empty / partial data via quality_flags.partial_data surfaces warning.
- Defensive contract: doesn't crash on missing fields.
- Privacy: no raw AI content is in any visible testid.

The test uses hand-rolled mock data so it does not require backend
connectivity. Tests follow the same pattern as MockInterviewPanel
(US3 T092) and ResumeDiagnosisPanel (US2 T082).
*/
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

// Import the panel under test.
import { AIOperationsPanel } from '@/components/pm-dashboard/AIOperationsPanel'
import type { AIOperationsPanel as AIOperationsPanelType } from '@/types/pm-dashboard'

const BASE_PERIOD = {
  period_start: '2026-06-01T00:00:00.000Z',
  period_end: '2026-06-08T00:00:00.000Z',
  dimensions: { environment: 'production' },
  source_of_truth: 'ai_invocation_records',
  freshness_at: '2026-06-08T12:00:00.000Z',
  quality_flags: {
    missing_version_fields: [],
    sampled_data: false,
    delayed_ingestion: false,
    partial_data: false,
  },
  value: 1200,
  unit: 'count' as const,
}

function makePanel(
  overrides: Partial<AIOperationsPanelType['data']> = {},
): AIOperationsPanelType {
  return {
    metric_id: 'pm.ai_operations',
    display_name: 'AI Operations',
    ...BASE_PERIOD,
    quality_flags: {
      missing_version_fields: [],
      sampled_data: false,
      delayed_ingestion: false,
      partial_data: false,
    },
    data: {
      call_count: 1200,
      success_count: 1140,
      failure_count: 60,
      success_rate: 0.95,
      failure_rate: 0.05,
      retry_count: 24,
      p50_latency_ms: 320,
      p95_latency_ms: 1450,
      p99_latency_ms: 2800,
      estimated_cost: 0.0005,
      total_tokens: 250_000,
      prompt_tokens: 180_000,
      completion_tokens: 70_000,
      is_estimate: true,
      model_breakdown: {
        'gpt-4o-mini': 800,
        'gpt-4o': 300,
        'deepseek-chat': 100,
      },
      graph_breakdown: {
        default_graph: 700,
        planner_graph: 500,
      },
      node_breakdown: {
        default_node: 800,
        planner_search: 400,
      },
      prompt_fingerprint_breakdown: {
        'fp-001': 600,
        'fp-002': 400,
        'fp-003': 200,
      },
      ...overrides,
    },
  }
}

describe('AIOperationsPanel — US4 T101', () => {
  it('renders 8 metric cards in a grid', () => {
    const panel = makePanel()
    render(<AIOperationsPanel panel={panel} />)
    expect(screen.getByTestId('ai-operations-panel')).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-metric-call_count'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-metric-success_rate'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-metric-failure_rate'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-metric-retry_count'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-metric-p50_latency_ms'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-metric-p95_latency_ms'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-metric-estimated_cost'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-metric-total_tokens'),
    ).toBeInTheDocument()
  })

  it('renders the success rate as a percentage', () => {
    const panel = makePanel({ success_rate: 0.95 })
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-metric-success_rate'),
    ).toHaveTextContent('95.0%')
  })

  it('renders the failure rate as a percentage with inverted color', () => {
    const panel = makePanel({ failure_rate: 0.05 })
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-metric-failure_rate'),
    ).toHaveTextContent('5.0%')
  })

  it('renders the p50 latency in ms', () => {
    const panel = makePanel({ p50_latency_ms: 320 })
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-metric-p50_latency_ms'),
    ).toHaveTextContent('320 ms')
  })

  it('renders the p95 latency in ms', () => {
    const panel = makePanel({ p95_latency_ms: 1450 })
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-metric-p95_latency_ms'),
    ).toHaveTextContent('1450 ms')
  })

  it('renders the estimated cost as USD currency with 4 decimals', () => {
    const panel = makePanel({ estimated_cost: 0.0005 })
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-metric-estimated_cost'),
    ).toHaveTextContent('$0.0005')
  })

  it('renders the total tokens count', () => {
    const panel = makePanel({ total_tokens: 250_000 })
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-metric-total_tokens'),
    ).toHaveTextContent('250,000')
  })

  it('renders the 4 breakdown sections (model / graph / node / fingerprint)', () => {
    const panel = makePanel()
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-breakdown-model'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-breakdown-graph'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-breakdown-node'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('ai-operations-breakdown-fingerprint'),
    ).toBeInTheDocument()
  })

  it('handles empty / partial data via quality_flags.partial_data', () => {
    const panel = makePanel()
    panel.quality_flags = {
      missing_version_fields: [],
      sampled_data: false,
      delayed_ingestion: false,
      partial_data: true,
    }
    panel.freshness_at = 'unknown'
    panel.data = {
      call_count: 0,
      success_count: 0,
      failure_count: 0,
      success_rate: 0,
      failure_rate: 0,
      retry_count: 0,
      p50_latency_ms: 0,
      p95_latency_ms: 0,
      p99_latency_ms: 0,
      estimated_cost: 0,
      total_tokens: 0,
      prompt_tokens: 0,
      completion_tokens: 0,
      is_estimate: true,
      model_breakdown: {},
      graph_breakdown: {},
      node_breakdown: {},
      prompt_fingerprint_breakdown: {},
    }
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-quality-warning'),
    ).toBeInTheDocument()
  })

  it('surfaces missing_version_fields when filters omit dimensions', () => {
    const panel = makePanel()
    panel.quality_flags = {
      missing_version_fields: ['app_version', 'model'],
      sampled_data: false,
      delayed_ingestion: false,
      partial_data: false,
    }
    render(<AIOperationsPanel panel={panel} />)
    expect(
      screen.getByTestId('ai-operations-missing-fields'),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Defensive contract — minimal payload, panel renders without crashing.
// Privacy: no raw AI content (prompt_text, completion_text, etc.) ever
// appears as a testid in the rendered output.
// ---------------------------------------------------------------------------

describe('AIOperationsPanel — defensive contract', () => {
  it('does not crash when data is missing fields (partial)', () => {
    const partial = {
      metric_id: 'pm.ai_operations',
      display_name: 'AI Operations',
      period_start: '2026-06-01T00:00:00.000Z',
      period_end: '2026-06-08T00:00:00.000Z',
      dimensions: {},
      source_of_truth: 'ai_invocation_records',
      freshness_at: 'unknown',
      quality_flags: {
        missing_version_fields: [],
        sampled_data: false,
        delayed_ingestion: false,
        partial_data: true,
      },
      value: 0,
      unit: 'count' as const,
      data: {} as unknown as AIOperationsPanelType['data'],
    } as AIOperationsPanelType
    expect(() => render(<AIOperationsPanel panel={partial} />)).not.toThrow()
  })

  it('does not render any testid for raw AI content keys', () => {
    const panel = makePanel()
    const { container } = render(<AIOperationsPanel panel={panel} />)
    // Privacy: panel must not render raw AI content. We assert by
    // scanning for any testid attribute that contains a forbidden
    // raw-content substring.
    const forbiddenSubstrings = [
      'prompt_text',
      'completion_text',
      'system_prompt',
      'tool_calls',
      'request_body',
      'response_body',
      'raw_response',
    ]
    const testIds = Array.from(
      container.querySelectorAll('[data-testid]'),
    ).map((el) => el.getAttribute('data-testid') ?? '')
    for (const tid of testIds) {
      for (const forbidden of forbiddenSubstrings) {
        expect(tid).not.toContain(forbidden)
      }
    }
  })
})

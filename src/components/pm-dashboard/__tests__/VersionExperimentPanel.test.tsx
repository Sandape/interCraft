/** REQ-033 US7 T124 — VersionExperimentPanel tests.

Verifies the VersionExperimentPanel renders the US7 contract:

1. 5 metric cards: event_count + 4 distinct dimension counts
   (prompt_fingerprints / models / app_versions / experiments).
2. 2 breakdown tables: version_breakdown + experiment_breakdown.
3. "trace unavailable" badge when no OTel trace is active.
4. Empty / partial data via quality_flags.partial_data surfaces warning.
5. Defensive contract: doesn't crash on missing fields.
6. Source-of-truth label visible.

The test uses hand-rolled mock data so it does not require backend
connectivity. Tests follow the same pattern as AIOperationsPanel
(US4 T101), MockInterviewPanel (US3 T092), and ResumeDiagnosisPanel
(US2 T082).
*/
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

// Import the panel under test.
import { VersionExperimentPanel } from '@/components/pm-dashboard/VersionExperimentPanel'
import type { VersionExperimentPanel as VersionExperimentPanelType } from '@/types/pm-dashboard'

const BASE_PERIOD = {
  period_start: '2026-06-01T00:00:00.000Z',
  period_end: '2026-06-08T00:00:00.000Z',
  dimensions: { environment: 'production' },
  source_of_truth: 'product_events (grouped by version_context)',
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
  overrides: Partial<VersionExperimentPanelType['data']> = {},
  quality_flags: Partial<VersionExperimentPanelType['quality_flags']> = {},
): VersionExperimentPanelType {
  return {
    metric_id: 'pm.version_experiment',
    display_name: 'Version & Experiment',
    ...BASE_PERIOD,
    quality_flags: {
      missing_version_fields: [],
      sampled_data: false,
      delayed_ingestion: false,
      partial_data: false,
      ...quality_flags,
    },
    data: {
      event_count: 1200,
      distinct_prompt_fingerprints: 5,
      distinct_models: 3,
      distinct_app_versions: 4,
      distinct_experiments: 2,
      top_versions: [
        {
          prompt_fingerprint: 'fp-001',
          rubric_version: 'v1',
          app_version: '0.3.0',
          model: 'deepseek-chat',
          count: 800,
        },
        {
          prompt_fingerprint: 'fp-002',
          rubric_version: 'v1',
          app_version: '0.3.0',
          model: 'deepseek-chat',
          count: 300,
        },
        {
          prompt_fingerprint: 'fp-003',
          rubric_version: 'v2',
          app_version: '0.4.0',
          model: 'gpt-4o',
          count: 100,
        },
      ],
      top_experiments: [
        { experiment_id: 'exp-A', count: 700 },
        { experiment_id: 'exp-B', count: 400 },
        { experiment_id: 'unknown', count: 100 },
      ],
      trace_available: true,
      top_versions_source:
        'ai_invocation_records (grouped by version_context)',
      ...overrides,
    },
  }
}

describe('VersionExperimentPanel — US7 T124', () => {
  it('renders 5 metric cards in a grid', () => {
    const panel = makePanel()
    render(<VersionExperimentPanel panel={panel} />)
    expect(screen.getByTestId('version-experiment-panel')).toBeInTheDocument()
    expect(
      screen.getByTestId('version-experiment-metric-event_count'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId(
        'version-experiment-metric-distinct_prompt_fingerprints',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('version-experiment-metric-distinct_models'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('version-experiment-metric-distinct_app_versions'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('version-experiment-metric-distinct_experiments'),
    ).toBeInTheDocument()
  })

  it('renders the version breakdown table with top 5 rows', () => {
    const panel = makePanel()
    render(<VersionExperimentPanel panel={panel} />)
    expect(
      screen.getByTestId('version-experiment-version-breakdown'),
    ).toBeInTheDocument()
    const rows = screen.getAllByTestId('version-experiment-version-row')
    expect(rows.length).toBe(3)
  })

  it('renders the experiment breakdown table with top 5 rows', () => {
    const panel = makePanel()
    render(<VersionExperimentPanel panel={panel} />)
    expect(
      screen.getByTestId('version-experiment-experiment-breakdown'),
    ).toBeInTheDocument()
    const rows = screen.getAllByTestId('version-experiment-experiment-row')
    expect(rows.length).toBe(3)
  })

  it('shows the trace-unavailable badge when no OTel trace is active', () => {
    const panel = makePanel({ trace_available: false })
    render(<VersionExperimentPanel panel={panel} />)
    expect(
      screen.getByTestId('version-experiment-trace-unavailable'),
    ).toBeInTheDocument()
  })

  it('does NOT show the trace-unavailable badge when a trace is active', () => {
    const panel = makePanel({ trace_available: true })
    render(<VersionExperimentPanel panel={panel} />)
    expect(
      screen.queryByTestId('version-experiment-trace-unavailable'),
    ).not.toBeInTheDocument()
  })

  it('handles empty / partial data via quality_flags.partial_data', () => {
    const panel = makePanel(
      {
        event_count: 0,
        distinct_prompt_fingerprints: 0,
        distinct_models: 0,
        distinct_app_versions: 0,
        distinct_experiments: 0,
        top_versions: [],
        top_experiments: [],
        trace_available: false,
      },
      { partial_data: true },
    )
    panel.freshness_at = 'unknown'
    render(<VersionExperimentPanel panel={panel} />)
    expect(
      screen.getByTestId('version-experiment-quality-warning'),
    ).toBeInTheDocument()
    // Empty breakdown rows.
    expect(
      screen.getByTestId('version-experiment-version-empty'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('version-experiment-experiment-empty'),
    ).toBeInTheDocument()
  })

  it('surfaces missing_version_fields when filters omit dimensions', () => {
    const panel = makePanel(
      {},
      { missing_version_fields: ['app_version', 'model'] },
    )
    render(<VersionExperimentPanel panel={panel} />)
    expect(
      screen.getByTestId('version-experiment-missing-fields'),
    ).toBeInTheDocument()
  })

  it('renders the source-of-truth label', () => {
    const panel = makePanel()
    render(<VersionExperimentPanel panel={panel} />)
    expect(
      screen.getByTestId('version-experiment-source-of-truth'),
    ).toHaveTextContent('product_events')
  })

  it('formats the version row keys as fingerprint / rubric / app / model', () => {
    const panel = makePanel()
    render(<VersionExperimentPanel panel={panel} />)
    const firstRow = screen.getAllByTestId('version-experiment-version-row')[0]
    expect(firstRow).toHaveTextContent('fp-001')
    expect(firstRow).toHaveTextContent('v1')
    expect(firstRow).toHaveTextContent('0.3.0')
    expect(firstRow).toHaveTextContent('deepseek-chat')
    expect(firstRow).toHaveTextContent('800')
  })
})

// ---------------------------------------------------------------------------
// Defensive contract — minimal payload, panel renders without crashing.
// ---------------------------------------------------------------------------

describe('VersionExperimentPanel — defensive contract', () => {
  it('does not crash when data is missing fields (partial)', () => {
    const partial = {
      metric_id: 'pm.version_experiment',
      display_name: 'Version & Experiment',
      period_start: '2026-06-01T00:00:00.000Z',
      period_end: '2026-06-08T00:00:00.000Z',
      dimensions: {},
      source_of_truth: 'product_events (grouped by version_context)',
      freshness_at: 'unknown',
      quality_flags: {
        missing_version_fields: [],
        sampled_data: false,
        delayed_ingestion: false,
        partial_data: true,
      },
      value: 0,
      unit: 'count' as const,
      data: {} as unknown as VersionExperimentPanelType['data'],
    } as VersionExperimentPanelType
    expect(() =>
      render(<VersionExperimentPanel panel={partial} />),
    ).not.toThrow()
  })
})
/** REQ-033 US3 T092 — MockInterviewPanel tests.

Verifies the MockInterviewPanel renders the 5 core metrics per US3:

1. Session starts (count)
2. Completions (count)
3. Completion rate (completions / starts)
4. Avg question count
5. Failure rate + retries
Plus: Report views (count).

Tests cover:
- All 6 metric cards rendered in a grid.
- Completion rate displayed as percentage.
- Failure rate displayed as percentage with color coding.
- Empty / partial data via quality_flags.partial_data surfaces warning.
- Defensive contract: does not crash on missing fields.

The test uses hand-rolled mock data so it does not require backend
connectivity. Tests follow the same pattern as ResumeDiagnosisPanel
US2 tests.
*/
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

// Import the panel under test.
import { MockInterviewPanel } from '@/components/pm-dashboard/MockInterviewPanel'
import type { MockInterviewPanel as MockInterviewPanelType } from '@/types/pm-dashboard'

const BASE_PERIOD = {
  period_start: '2026-06-01T00:00:00.000Z',
  period_end: '2026-06-08T00:00:00.000Z',
  dimensions: { environment: 'production' },
  source_of_truth: 'product_events (interview.*)',
  freshness_at: '2026-06-08T12:00:00.000Z',
  quality_flags: {
    missing_version_fields: [],
    sampled_data: false,
    delayed_ingestion: false,
    partial_data: false,
  },
  value: 120,
  unit: 'count' as const,
}

function makePanel(
  overrides: Partial<MockInterviewPanelType['data']> = {},
): MockInterviewPanelType {
  return {
    metric_id: 'pm.mock_interview',
    display_name: 'Mock Interview',
    ...BASE_PERIOD,
    quality_flags: {
      missing_version_fields: [],
      sampled_data: false,
      delayed_ingestion: false,
      partial_data: false,
    },
    data: {
      starts: 120,
      completions: 96,
      completion_rate: 0.8,
      avg_question_count: 7.5,
      report_views: 80,
      retries: 12,
      failure_rate: 0.1,
      failure_categories: { timeout: 6, llm_error: 6 },
      ...overrides,
    },
  }
}

describe('MockInterviewPanel — US3 T092', () => {
  it('renders 6 metric cards in a grid', () => {
    const panel = makePanel()
    render(<MockInterviewPanel panel={panel} />)
    expect(screen.getByTestId('mock-interview-panel')).toBeInTheDocument()
    expect(
      screen.getByTestId('mock-interview-metric-starts'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('mock-interview-metric-completions'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('mock-interview-metric-completion_rate'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('mock-interview-metric-avg_question_count'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('mock-interview-metric-report_views'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('mock-interview-metric-failure_rate'),
    ).toBeInTheDocument()
  })

  it('renders the completion rate as a percentage', () => {
    const panel = makePanel({ completion_rate: 0.875 })
    render(<MockInterviewPanel panel={panel} />)
    expect(
      screen.getByTestId('mock-interview-metric-completion_rate'),
    ).toHaveTextContent('87.5%')
  })

  it('renders the failure rate as a percentage', () => {
    const panel = makePanel({ failure_rate: 0.1 })
    render(<MockInterviewPanel panel={panel} />)
    expect(
      screen.getByTestId('mock-interview-metric-failure_rate'),
    ).toHaveTextContent('10.0%')
  })

  it('renders the avg question count as a decimal', () => {
    const panel = makePanel({ avg_question_count: 7.5 })
    render(<MockInterviewPanel panel={panel} />)
    expect(
      screen.getByTestId('mock-interview-metric-avg_question_count'),
    ).toHaveTextContent('7.5')
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
      starts: 0,
      completions: 0,
      completion_rate: 0,
      avg_question_count: 0,
      report_views: 0,
      retries: 0,
      failure_rate: 0,
      failure_categories: {},
    }
    render(<MockInterviewPanel panel={panel} />)
    expect(
      screen.getByTestId('mock-interview-quality-warning'),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Defensive contract — minimal payload, panel renders without crashing.
// ---------------------------------------------------------------------------

describe('MockInterviewPanel — defensive contract', () => {
  it('does not crash when data is missing fields (partial)', () => {
    const partial = {
      metric_id: 'pm.mock_interview',
      display_name: 'Mock Interview',
      period_start: '2026-06-01T00:00:00.000Z',
      period_end: '2026-06-08T00:00:00.000Z',
      dimensions: {},
      source_of_truth: 'product_events',
      freshness_at: 'unknown',
      quality_flags: {
        missing_version_fields: [],
        sampled_data: false,
        delayed_ingestion: false,
        partial_data: true,
      },
      value: 0,
      unit: 'count' as const,
      data: {} as unknown as MockInterviewPanelType['data'],
    } as MockInterviewPanelType
    expect(() => render(<MockInterviewPanel panel={partial} />)).not.toThrow()
  })
})
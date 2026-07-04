/**
 * Static-guard unit tests for REQ-044 US7 / FR-027~FR-030.
 *
 * Verifies:
 *
 *   - MetricTooltip renders the 10 FR-027 fields with "(not provided)"
 *     sentinels for missing values (AC-27.1 + AC-27.4).
 *   - QualityFlagsBadge renders 5 states (AC-28.1).
 *   - SnapshotCard shows snapshot_id / workspace / late-arriving /
 *     cohort_change warnings (AC-29.1 + EC-1/EC-2).
 *   - SnapshotGenerateForm has workspace selector + filter picker +
 *     annotations textarea + format selector (AC-29.5).
 *   - DeltaIndicator renders delta_pct + late-arriving warning
 *     (AC-30.3 + EC-1).
 *   - SnapshotViewer renders FrozenValueTable + CurrentValueTable +
 *     comparison_deltas + cohort change banner + late-arriving
 *     banner + freshness warning banner (AC-30.2 + EC-1/EC-2).
 *   - SnapshotViewer renders snapshot-failed banner on error
 *     (EC-4).
 *
 * Backend service integration is covered by backend pytest; these
 * tests are the CI-friendly component smoke check.
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MetricTooltip } from '../MetricTooltip'
import { QualityFlagsBadge } from '@/admin/components/governance/QualityFlagsBadge'
import { SnapshotCard } from '../SnapshotCard'
import { SnapshotGenerateForm } from '../SnapshotGenerateForm'
import { DeltaIndicator } from '../DeltaIndicator'
import { SnapshotViewer } from '../SnapshotViewer'
import type { ReviewSnapshotResponse } from '@/types/admin-review-snapshots'

// Wrapper to provide QueryClient for components that use react-query hooks.
function withQueryClient(node: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>
}

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const sampleMetric = {
  metric_id: 'pm.ai.ai_task_success_rate',
  name: 'AI Task Success Rate',
  definition: 'Fraction of AI tasks with status=success in the snapshot window.',
  owner: 'ai-team',
  source: 'telemetry:ai.call_completed',
  numerator: 'ai tasks where status=success',
  denominator: 'ai tasks (all statuses)',
  unit: 'percent',
  period: 'rolling 7d',
  freshness: 'updated every 30 minutes',
  completeness: '99% (only ai-team scoped tasks)',
  quality_flags: 'valid_zero' as const,
}

const sampleMetricMissing = {
  metric_id: 'm-test',
  name: 'test',
  // other 9 fields missing -> render as NOT_PROVIDED
  definition: '',
  owner: '',
  source: '',
  numerator: '',
  denominator: '',
  unit: '',
  period: '',
  freshness: '',
  completeness: '',
  quality_flags: 'missing' as const,
}

const sampleSnapshot: ReviewSnapshotResponse = {
  snapshot_id: 'snap-000001',
  workspace: 'command-center',
  generated_at: '2026-07-04T10:00:00Z',
  generated_by: '@user:pm1',
  filters: { period: 'rolling_7d' },
  frozen_values: [
    {
      metric_id: 'pm.command-center.decision_queue_depth',
      value: 50,
      unit: 'count',
      captured_at: '2026-07-02T10:00:00Z',
      data_status: 'valid_zero',
    },
  ],
  comparison_deltas: [
    {
      metric_id: 'pm.command-center.decision_queue_depth',
      delta_pct: 12.0,
      period: 'vs prior week',
    },
  ],
  metric_definitions: [sampleMetric],
  freshness_warnings: ['stale window detected'],
  quality_flags: { 'pm.command-center.decision_queue_depth': 'valid_zero' },
  annotations: 'Weekly PM sync — command-center pulse',
  evidence_links: [
    { label: 'INC-2026-001 activation regression', kind: 'incident', target_id: 'INC-2026-001' },
  ],
  current_values: [
    {
      metric_id: 'pm.command-center.decision_queue_depth',
      value: 56,
      unit: 'count',
      captured_at: '2026-07-04T10:00:00Z',
      data_status: 'valid_zero',
    },
  ],
  cohort_definition_changed: false,
  cohort_change_warning: null,
  late_arriving_warnings: ['decision_queue_depth increased by 12.0% since snapshot'],
  download_url: '/api/v1/admin-console/governance/exports/snap-000001/download',
  expires_at: '2026-07-05T10:00:00Z',
  data_status: 'valid_zero',
  visibility_mode: 'full',
  comparison_period: 'vs prior week',
}

// ---------------------------------------------------------------------------
// AC-27.1 — MetricTooltip 10 fields
// ---------------------------------------------------------------------------

describe('MetricTooltip (FR-027 AC-27.1)', () => {
  it('renders the 10 FR-027 fields when fully populated', () => {
    render(<MetricTooltip metric={sampleMetric} />)
    expect(screen.getByText('Definition')).toBeTruthy()
    expect(screen.getByText('Owner')).toBeTruthy()
    expect(screen.getByText('Source')).toBeTruthy()
    expect(screen.getByText('Numerator')).toBeTruthy()
    expect(screen.getByText('Denominator')).toBeTruthy()
    expect(screen.getByText('Unit')).toBeTruthy()
    expect(screen.getByText('Period')).toBeTruthy()
    expect(screen.getByText('Freshness')).toBeTruthy()
    expect(screen.getByText('Completeness')).toBeTruthy()
    expect(screen.getByText('Quality Flags')).toBeTruthy()
  })

  it('renders "(not provided)" for missing fields (AC-27.4)', () => {
    render(<MetricTooltip metric={sampleMetricMissing} />)
    const notProvidedCells = screen.getAllByText('(not provided)')
    expect(notProvidedCells.length).toBeGreaterThanOrEqual(9)
  })

  it('data-missing=true flag is set on missing cells (AC-27.4)', () => {
    const { container } = render(<MetricTooltip metric={sampleMetricMissing} />)
    const missingValues = container.querySelectorAll('[data-missing="true"]')
    expect(missingValues.length).toBeGreaterThanOrEqual(9)
  })
})

// ---------------------------------------------------------------------------
// AC-28.1 — QualityFlagsBadge 5 states
// ---------------------------------------------------------------------------

describe('QualityFlagsBadge (FR-028 AC-28.1)', () => {
  const states = ['valid_zero', 'missing', 'partial', 'stale', 'failed'] as const
  states.forEach((s) => {
    it(`renders ${s} state`, () => {
      render(<QualityFlagsBadge status={s} />)
      expect(screen.getByText(s.replace('_', ' '))).toBeTruthy()
    })
  })
})

// ---------------------------------------------------------------------------
// AC-29.1 — SnapshotCard surfaces
// ---------------------------------------------------------------------------

describe('SnapshotCard (FR-029 AC-29.1)', () => {
  it('renders snapshot_id and workspace', () => {
    render(<SnapshotCard snapshot={sampleSnapshot} />)
    expect(screen.getByText(/command-center/)).toBeTruthy()
    expect(screen.getByText(/snap-000001/)).toBeTruthy()
  })

  it('renders late-arriving warning when present (EC-1)', () => {
    render(<SnapshotCard snapshot={sampleSnapshot} />)
    expect(screen.getByTestId('late-arriving-warning')).toBeTruthy()
  })

  it('renders freshness warning when present', () => {
    render(<SnapshotCard snapshot={sampleSnapshot} />)
    expect(screen.getByTestId('freshness-warning')).toBeTruthy()
  })

  it('renders cohort change warning when cohort_definition_changed=True (EC-2)', () => {
    const snap = { ...sampleSnapshot, cohort_definition_changed: true }
    render(<SnapshotCard snapshot={snap} />)
    expect(screen.getByTestId('cohort-change-warning')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// AC-29.5 — SnapshotGenerateForm
// ---------------------------------------------------------------------------

describe('SnapshotGenerateForm (FR-029 AC-29.5)', () => {
  it('renders workspace selector', () => {
    render(withQueryClient(<SnapshotGenerateForm />))
    expect(screen.getByTestId('workspace-selector')).toBeTruthy()
  })

  it('renders comparison period selector', () => {
    render(withQueryClient(<SnapshotGenerateForm />))
    expect(screen.getByTestId('comparison-period-selector')).toBeTruthy()
  })

  it('renders format selector', () => {
    render(withQueryClient(<SnapshotGenerateForm />))
    expect(screen.getByTestId('format-selector')).toBeTruthy()
  })

  it('renders annotations textarea', () => {
    render(withQueryClient(<SnapshotGenerateForm />))
    expect(screen.getByTestId('annotations-textarea')).toBeTruthy()
  })

  it('renders filter picker with cohort_changed + expired_record_ids', () => {
    render(withQueryClient(<SnapshotGenerateForm />))
    expect(screen.getByTestId('filter-picker')).toBeTruthy()
    expect(screen.getByTestId('cohort-changed-checkbox')).toBeTruthy()
    expect(screen.getByTestId('expired-record-ids-input')).toBeTruthy()
  })

  it('renders generate submit button', () => {
    render(withQueryClient(<SnapshotGenerateForm />))
    expect(screen.getByTestId('generate-snapshot-btn')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// AC-30.3 — DeltaIndicator
// ---------------------------------------------------------------------------

describe('DeltaIndicator (FR-030 AC-30.3)', () => {
  it('renders delta_pct', () => {
    const delta = {
      metric_id: 'm1',
      delta_pct: 12.0,
      period: 'vs prior week',
    }
    render(<DeltaIndicator delta={delta} />)
    expect(screen.getByText(/\+12\.0%/)).toBeTruthy()
  })

  it('renders late-arriving warning when delta exceeds tolerance (EC-1)', () => {
    const delta = {
      metric_id: 'm1',
      delta_pct: 12.0,
      period: 'vs prior week',
    }
    render(<DeltaIndicator delta={delta} />)
    expect(screen.getByTestId('late-arriving')).toBeTruthy()
  })

  it('does NOT render late-arriving warning when delta within tolerance', () => {
    const delta = {
      metric_id: 'm1',
      delta_pct: 0.1,
      period: 'vs prior week',
    }
    render(<DeltaIndicator delta={delta} />)
    expect(screen.queryByTestId('late-arriving')).toBeNull()
  })

  it('renders negative delta with "down" prefix', () => {
    const delta = {
      metric_id: 'm1',
      delta_pct: -5.5,
      period: 'vs prior week',
    }
    render(<DeltaIndicator delta={delta} />)
    expect(screen.getByText(/-5\.5%/)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// AC-30.2 / EC-1 / EC-2 — SnapshotViewer
// ---------------------------------------------------------------------------

describe('SnapshotViewer (FR-030 AC-30.2 + EC-1/EC-2/EC-4)', () => {
  it('renders frozen and current value tables (AC-30.2)', () => {
    render(<SnapshotViewer snapshot={sampleSnapshot} />)
    expect(screen.getByTestId('frozen-value-table')).toBeTruthy()
    expect(screen.getByTestId('current-value-table')).toBeTruthy()
  })

  it('renders comparison deltas', () => {
    render(<SnapshotViewer snapshot={sampleSnapshot} />)
    expect(screen.getByTestId('comparison-deltas')).toBeTruthy()
  })

  it('renders late-arriving banner (EC-1)', () => {
    render(<SnapshotViewer snapshot={sampleSnapshot} />)
    expect(screen.getByTestId('late-arriving-banner')).toBeTruthy()
  })

  it('renders freshness warning banner', () => {
    render(<SnapshotViewer snapshot={sampleSnapshot} />)
    expect(screen.getByTestId('freshness-warning-banner')).toBeTruthy()
  })

  it('renders cohort change banner when cohort_definition_changed=True (EC-2)', () => {
    const snap = {
      ...sampleSnapshot,
      cohort_definition_changed: true,
      cohort_change_warning: 'cohort definition changed since snapshot: foo, bar',
    }
    render(<SnapshotViewer snapshot={snap} />)
    expect(screen.getByTestId('cohort-change-warning-banner')).toBeTruthy()
  })

  it('renders evidence link list (SC-012)', () => {
    render(<SnapshotViewer snapshot={sampleSnapshot} />)
    expect(screen.getByTestId('evidence-links-list')).toBeTruthy()
  })

  it('renders snapshot-failed banner when error is provided (EC-4)', () => {
    render(
      <SnapshotViewer
        snapshot={null}
        error={new Error('backend unreachable')}
        onRetry={() => undefined}
      />,
    )
    expect(screen.getByTestId('snapshot-failed')).toBeTruthy()
    expect(screen.getByTestId('snapshot-failed-retry')).toBeTruthy()
    expect(screen.getByTestId('snapshot-retry-btn')).toBeTruthy()
  })

  it('renders loading state when loading=true', () => {
    render(<SnapshotViewer snapshot={null} loading={true} />)
    expect(screen.getByTestId('snapshot-viewer-loading')).toBeTruthy()
  })
})
/**
 * Static-guard unit tests for REQ-044 US2 / FR-011~FR-015.
 *
 * These tests do NOT need the backend running; they verify:
 *
 *   - 7 question tabs render distinct testids
 *   - QuestionTabBar switches active tab via callback
 *   - FunnelChart renders 5 steps + zero-funnel banner for EC-1
 *   - CohortPicker shows stale warning for EC-2
 *   - FeatureAdoptionGrid renders 5 metric cards (NOT a single score)
 *   - FeatureAdoptionGrid shows Insufficient data badge for EC-3
 *   - MetricTooltip renders all 7 SC-004 fields
 *   - UserDetailDrawer renders visibility levels (full/masked/hidden)
 *
 * Playwright E2E covers the full HTTP round-trip; these tests act
 * as a CI-friendly smoke check before the Playwright suite runs.
 */
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QuestionTabBar } from '../QuestionTabBar'
import { FunnelChart } from '../FunnelChart'
import { CohortPicker } from '../CohortPicker'
import { FeatureAdoptionGrid } from '../FeatureAdoptionGrid'
import { MetricTooltip } from '../MetricTooltip'
import { UserDetailDrawer } from '../../users/UserDetailDrawer'
import type {
  CohortSegment,
  FeatureAdoptionRow,
  FunnelResponse,
  UserPrivacySafe,
} from '@/types/admin-product-analytics'

describe('REQ-044 US2 / FR-011 QuestionTabBar', () => {
  it('renders all 7 question tabs', () => {
    render(<QuestionTabBar activeTab="funnel" onChange={vi.fn()} />)
    for (const tab of [
      'activation',
      'funnel',
      'retention',
      'adoption',
      'journey',
      'release',
      'experiment',
    ]) {
      expect(screen.getByTestId(`question-tab-${tab}`)).toBeInTheDocument()
    }
  })

  it('marks the active tab', () => {
    render(<QuestionTabBar activeTab="adoption" onChange={vi.fn()} />)
    expect(screen.getByTestId('question-tab-adoption').getAttribute('data-active')).toBe('true')
    expect(screen.getByTestId('question-tab-funnel').getAttribute('data-active')).toBe('false')
  })

  it('invokes onChange when a tab is clicked', () => {
    const onChange = vi.fn()
    render(<QuestionTabBar activeTab="funnel" onChange={onChange} />)
    fireEvent.click(screen.getByTestId('question-tab-retention'))
    expect(onChange).toHaveBeenCalledWith('retention')
  })
})

describe('REQ-044 US2 / FR-012 FunnelChart', () => {
  const sampleFunnel: FunnelResponse = {
    funnelId: 'q-fun-1',
    steps: [
      { stepName: 'registered', count: 1842, stepConversion: null, dropOff: null },
      { stepName: 'login', count: 1655, stepConversion: 0.8985, dropOff: 0.1015 },
      { stepName: 'create_resume', count: 1283, stepConversion: 0.7752, dropOff: 0.1233 },
      { stepName: 'book_interview', count: 782, stepConversion: 0.6095, dropOff: 0.1657 },
      { stepName: 'complete_interview', count: 528, stepConversion: 0.6752, dropOff: 0.3248 },
    ],
    entryConversion: 0.2867,
    comparisonDelta: {
      comparisonPeriodLabel: '前 7 天',
      stepConversionDelta: -0.025,
    },
    timeToConvert: {
      p50Seconds: 86400,
      ci95LowerSeconds: 72000,
      ci95UpperSeconds: 108000,
      sampleSize: 528,
    },
    cohortId: 'cohort-registered',
    cohortPopulation: 1842,
    lastComputedAt: '2026-07-04T10:00:00Z',
    freshnessAt: '2026-07-04T10:00:00Z',
  }

  it('renders 5 funnel steps', () => {
    render(<FunnelChart funnel={sampleFunnel} cohortName="近 7 天注册用户" />)
    expect(screen.getByTestId('funnel-step-registered')).toBeInTheDocument()
    expect(screen.getByTestId('funnel-step-login')).toBeInTheDocument()
    expect(screen.getByTestId('funnel-step-create_resume')).toBeInTheDocument()
    expect(screen.getByTestId('funnel-step-book_interview')).toBeInTheDocument()
    expect(screen.getByTestId('funnel-step-complete_interview')).toBeInTheDocument()
  })

  it('renders entry conversion + comparison delta + T2C', () => {
    render(<FunnelChart funnel={sampleFunnel} />)
    expect(screen.getByTestId('funnel-entry-conversion').textContent).toMatch(/28.7%/)
    expect(screen.getByTestId('funnel-comparison-delta').textContent).toMatch(/-2.5%/)
    expect(screen.getByTestId('funnel-time-to-convert').textContent).toMatch(/P50/)
  })

  it('renders cohort tag + population + last_computed_at (AC-13.3)', () => {
    render(<FunnelChart funnel={sampleFunnel} />)
    expect(screen.getByTestId('funnel-cohort-population').textContent).toMatch(/1,842/)
    expect(screen.getByTestId('funnel-last-computed-at').textContent).toMatch(/2026-07-04/)
  })

  it('EC-1: zero funnel surfaces explicit "0 users entered" banner', () => {
    const zeroFunnel: FunnelResponse = {
      ...sampleFunnel,
      funnelId: 'funnel-empty',
      steps: sampleFunnel.steps.map((s) => ({ ...s, count: 0 })),
      entryConversion: 0,
    }
    render(<FunnelChart funnel={zeroFunnel} />)
    expect(screen.getByTestId('funnel-zero-banner').textContent).toMatch(/0 users entered/)
  })
})

describe('REQ-044 US2 / FR-013 CohortPicker', () => {
  const sampleCohorts: CohortSegment[] = [
    {
      id: 'cohort-active',
      name: '近 30 天活跃用户',
      definition: 'last_active_at >= now - 7d',
      population: 5234,
      owner: '@pm-oncall',
      lastComputedAt: '2026-07-04T10:00:00Z',
      stale: false,
    },
    {
      id: 'cohort-new',
      name: '近 14 天新用户 (stale)',
      definition: 'created_at >= now - 14d',
      population: 3621,
      owner: '@pm-oncall',
      lastComputedAt: '2026-07-02T10:00:00Z',
      stale: true,
    },
  ]

  it('renders the cohort select + all options', () => {
    render(
      <CohortPicker
        cohorts={sampleCohorts}
        selectedCohortId={null}
        onSelect={vi.fn()}
      />,
    )
    expect(screen.getByTestId('cohort-select')).toBeInTheDocument()
    expect(screen.getByTestId('cohort-option-cohort-active')).toBeInTheDocument()
    expect(screen.getByTestId('cohort-option-cohort-new')).toBeInTheDocument()
  })

  it('EC-2: stale cohort surfaces the "stale cohort" warning', () => {
    render(
      <CohortPicker
        cohorts={sampleCohorts}
        selectedCohortId="cohort-new"
        onSelect={vi.fn()}
      />,
    )
    expect(screen.getByTestId('cohort-stale-warning').textContent).toMatch(/stale cohort/)
  })

  it('invokes onSelect when a cohort is chosen', () => {
    const onSelect = vi.fn()
    render(
      <CohortPicker
        cohorts={sampleCohorts}
        selectedCohortId={null}
        onSelect={onSelect}
      />,
    )
    fireEvent.change(screen.getByTestId('cohort-select'), {
      target: { value: 'cohort-active' },
    })
    expect(onSelect).toHaveBeenCalledWith('cohort-active')
  })

  it('renders population + last_computed_at (AC-13.3)', () => {
    render(
      <CohortPicker
        cohorts={sampleCohorts}
        selectedCohortId="cohort-active"
        onSelect={vi.fn()}
      />,
    )
    expect(screen.getByTestId('cohort-population').textContent).toMatch(/5,234/)
    expect(screen.getByTestId('cohort-last-computed-at').textContent).toMatch(/2026-07-04/)
  })
})

describe('REQ-044 US2 / FR-014 FeatureAdoptionGrid', () => {
  const sampleRows: FeatureAdoptionRow[] = [
    {
      featureId: 'feat-error-book',
      featureName: '错误本',
      metrics: [
        {
          metricName: 'discovery_users',
          currentValue: 1543,
          unit: 'count',
          comparisonDelta: 0.012,
          sampleSize: 1543,
          insufficientData: false,
        },
        {
          metricName: 'first_use_users',
          currentValue: 1127,
          unit: 'count',
          comparisonDelta: 0.012,
          sampleSize: 1127,
          insufficientData: false,
        },
        {
          metricName: 'repeat_users',
          currentValue: 807,
          unit: 'count',
          comparisonDelta: 0.012,
          sampleSize: 807,
          insufficientData: false,
        },
        {
          metricName: 'frequency_avg',
          currentValue: 3.1,
          unit: 'per_user_per_week',
          comparisonDelta: 0.012,
          sampleSize: 807,
          insufficientData: false,
        },
        {
          metricName: 'downstream_success_rate',
          currentValue: 0.764,
          unit: 'rate',
          comparisonDelta: 0.012,
          sampleSize: 807,
          insufficientData: false,
        },
      ],
      cohortId: 'cohort-active',
      cohortPopulation: 5234,
      lastComputedAt: '2026-07-04T10:00:00Z',
      freshnessAt: '2026-07-04T10:00:00Z',
    },
    {
      featureId: 'feat-replay',
      featureName: '面试回放',
      metrics: [
        {
          metricName: 'discovery_users',
          currentValue: 95,
          unit: 'count',
          comparisonDelta: -0.023,
          sampleSize: 12,
          insufficientData: true,
        },
        {
          metricName: 'first_use_users',
          currentValue: 42,
          unit: 'count',
          comparisonDelta: -0.023,
          sampleSize: 12,
          insufficientData: true,
        },
        {
          metricName: 'repeat_users',
          currentValue: 12,
          unit: 'count',
          comparisonDelta: -0.023,
          sampleSize: 12,
          insufficientData: true,
        },
        {
          metricName: 'frequency_avg',
          currentValue: 0.6,
          unit: 'per_user_per_week',
          comparisonDelta: -0.023,
          sampleSize: 12,
          insufficientData: true,
        },
        {
          metricName: 'downstream_success_rate',
          currentValue: 0.681,
          unit: 'rate',
          comparisonDelta: -0.023,
          sampleSize: 12,
          insufficientData: true,
        },
      ],
      cohortId: 'cohort-active',
      cohortPopulation: 5234,
      lastComputedAt: '2026-07-04T10:00:00Z',
      freshnessAt: '2026-07-04T10:00:00Z',
    },
  ]

  it('AC-14.3: renders 5 SEPARATE metric cards per feature (no collapse)', () => {
    render(<FeatureAdoptionGrid rows={sampleRows} />)
    for (const metric of [
      'discovery_users',
      'first_use_users',
      'repeat_users',
      'frequency_avg',
      'downstream_success_rate',
    ]) {
      expect(
        screen.getByTestId(`feature-adoption-metric-feat-error-book-${metric}`),
      ).toBeInTheDocument()
    }
  })

  it('AC-14.2: each metric shows comparison delta', () => {
    render(<FeatureAdoptionGrid rows={sampleRows} />)
    const delta = screen.getByTestId(
      'feature-adoption-metric-feat-error-book-discovery_users',
    ).textContent
    expect(delta).toMatch(/\+1.2%/)
  })

  it('EC-3: shows "Insufficient data" badge when sample_size is below threshold', () => {
    render(<FeatureAdoptionGrid rows={sampleRows} />)
    expect(
      screen.getByTestId('feature-adoption-insufficient-data'),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId('feature-adoption-insufficient-feat-replay-discovery_users'),
    ).toBeInTheDocument()
  })
})

describe('REQ-044 US2 / SC-004 MetricTooltip', () => {
  it('renders all 7 SC-004 fields', () => {
    render(
      <MetricTooltip
        trigger={<span>metric</span>}
        definition="近 14 天新功能 5 维度"
        owner="@pm-oncall"
        source="adoption.feature_5metric"
        period="14d"
        freshness="2026-07-04T10:00:00Z"
        completeness="cohort-scoped"
        qualityFlag="valid"
      />,
    )
    for (const field of [
      'definition',
      'owner',
      'source',
      'period',
      'freshness',
      'completeness',
      'quality-flag',
    ]) {
      expect(
        screen.getByTestId(`metric-tooltip-field-${field}`),
      ).toBeInTheDocument()
      expect(
        screen.getByTestId(`metric-tooltip-value-${field}`),
      ).toBeInTheDocument()
    }
  })
})

describe('REQ-044 US2 / FR-015 UserDetailDrawer', () => {
  const sampleProfile: UserPrivacySafe = {
    userId: '019ec1be-0000-7000-8000-000000000001',
    fields: [
      { name: 'email', visibility: 'masked', value: 'demo***@intercraft.io' },
      { name: 'role', visibility: 'full', value: 'pm' },
      { name: 'journey_summary', visibility: 'full', value: '注册 → 首次模拟面试 (活跃)' },
      { name: 'incidents_count', visibility: 'full', value: '2' },
      { name: 'quality_score', visibility: 'full', value: '0.871' },
      { name: 'created_at', visibility: 'full', value: '2026-05-12T09:21:00Z' },
      { name: 'last_active_at', visibility: 'full', value: '2026-07-04T08:00:00Z' },
    ],
    cohortPopulation: 5234,
    lastComputedAt: '2026-07-04T10:00:00Z',
    freshnessAt: '2026-07-04T10:00:00Z',
  }

  it('renders all 7 allow-listed fields (AC-15.1)', () => {
    render(<UserDetailDrawer profile={sampleProfile} onClose={vi.fn()} />)
    for (const name of [
      'email',
      'role',
      'journey_summary',
      'incidents_count',
      'quality_score',
      'created_at',
      'last_active_at',
    ]) {
      expect(screen.getByTestId(`user-drawer-row-${name}`)).toBeInTheDocument()
    }
  })

  it('AC-15.3: each field row shows the visibility level', () => {
    render(<UserDetailDrawer profile={sampleProfile} onClose={vi.fn()} />)
    expect(screen.getByTestId('user-drawer-visibility-email').textContent).toMatch(/masked/)
    expect(screen.getByTestId('user-drawer-visibility-role').textContent).toMatch(/full/)
  })

  it('renders empty state when profile is null', () => {
    render(<UserDetailDrawer profile={null} onClose={vi.fn()} />)
    expect(screen.getByTestId('user-drawer-empty')).toBeInTheDocument()
  })
})
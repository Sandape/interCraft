/**
 * Static-guard unit tests for REQ-044 US3 / FR-016~FR-020.
 *
 * Verifies:
 *
 *   - KPITiles renders 4 tiles (AC-16.1)
 *   - KPITiles EC-1 "0 AI tasks" banner
 *   - VolumeByFeatureChart renders 4 area rows (AC-16.2)
 *   - FailureCategoriesPie renders 5 categories (AC-16.3)
 *   - LatencyBandsChart renders p50/p95/p99 columns (AC-16.4)
 *   - TokenUsageChart renders input vs output rows (AC-16.5)
 *   - CostSummaryCard renders total + EC-3 stale warning (AC-16.6)
 *   - VersionSelector renders 4 dimensions + AC-17.4 compare label (AC-17.1)
 *   - VersionSelector EC-2 surfaces "version unknown" badge
 *   - QualityIssueDrawer renders all 8 FR-018 link fields (AC-18.2)
 *   - CostQualityAlert only renders when flagged + alerts severity (AC-19.2)
 *   - EvalBadcaseSummary renders total_eval_runs + pass_rate + ≥5 badcases (AC-20.1/20.2)
 *
 * Backend service integration is covered by Playwright E2E; these
 * tests are the CI-friendly component smoke check.
 */
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { KPITiles } from '../KPITiles'
import { VolumeByFeatureChart } from '../VolumeByFeatureChart'
import { FailureCategoriesPie } from '../FailureCategoriesPie'
import { LatencyBandsChart } from '../LatencyBandsChart'
import { TokenUsageChart } from '../TokenUsageChart'
import { CostSummaryCard } from '../CostSummaryCard'
import { VersionSelector } from '../VersionSelector'
import { QualityIssueDrawer } from '../QualityIssueDrawer'
import { CostQualityAlert } from '../CostQualityAlert'
import { EvalBadcaseSummaryCard } from '../EvalBadcaseSummary'
import type {
  AIQualityIssue,
  CostQualityFlag,
  EvalBadcaseSummary,
  KPIBundle,
  VersionSelectorResponse,
} from '@/types/admin-ai-operations'

const sampleKpis: KPIBundle = {
  totalVolume: 2661,
  successRate: 0.879,
  p95LatencyMs: 5640,
  totalCostUsd: 2.4842,
  freshnessAt: '2026-07-04T10:00:00Z',
  isEstimate: true,
}

const sampleVersions: VersionSelectorResponse = {
  dimensions: [
    {
      dimension: 'prompt_fingerprint',
      knownValues: ['prompt-v3.0', 'prompt-v3.1', 'prompt-v3.2'],
      unknownCount: 128,
    },
    {
      dimension: 'rubric_version',
      knownValues: ['rubric-v3', 'rubric-v4', 'rubric-v4.1'],
      unknownCount: 42,
    },
    {
      dimension: 'model',
      knownValues: ['gpt-4o', 'gpt-4o-mini', 'deepseek-chat'],
      unknownCount: 8,
    },
    {
      dimension: 'app_version',
      knownValues: ['v3.0', 'v3.1', 'v3.2'],
      unknownCount: 15,
    },
  ],
  baselineLabel: 'last 7 days',
  freshnessAt: '2026-07-04T10:00:00Z',
}

const sampleIssue: AIQualityIssue = {
  issueId: 'aiq-001',
  title: '面试评估 prompt 在 rubric v4 切换后回归',
  evalVerdict: 'FAIL',
  badcaseId: 'bc-2026-07-001',
  affectedFeatureArea: 'mock_interview',
  affectedJourneyStep: 'interview.feedback_loop',
  owner: '@ai-pm',
  status: 'reviewing',
  recommendedAction: '复核 rubric v4.1 是否覆盖 5 评分维度',
  featureAreaDimension: 'mock_interview',
  detectedAt: '2026-07-02T10:00:00Z',
  severity: 'high',
  freshnessAt: '2026-07-04T10:00:00Z',
  badcaseDetailHref: '/admin-console/incidents-badcases?from=bc-2026-07-001',
  evalDetailHref: '/admin-console/incidents-badcases?from=eval-run-2026-07-04',
}

const sampleEvalSummary: EvalBadcaseSummary = {
  evalRunSummary: {
    totalRuns: 187,
    passRate: 0.834,
    openRuns: 12,
  },
  openBadcasesCount: 1,
  recentBadcases: [
    {
      badcaseId: 'bc-2026-07-006',
      featureArea: 'resume_render',
      evalVerdict: 'FAIL',
      status: 'open',
      openedAt: '2026-07-04T09:00:00Z',
      owner: '@resume-pm',
    },
    {
      badcaseId: 'bc-2026-07-005',
      featureArea: 'error_coach',
      evalVerdict: 'MARGINAL',
      status: 'reviewing',
      openedAt: '2026-07-04T09:30:00Z',
      owner: '@error-book-pm',
    },
    {
      badcaseId: 'bc-2026-07-004',
      featureArea: 'mock_interview',
      evalVerdict: 'FAIL',
      status: 'regressing',
      openedAt: '2026-07-03T10:00:00Z',
      owner: '@ai-pm',
    },
    {
      badcaseId: 'bc-2026-07-003',
      featureArea: 'error_coach',
      evalVerdict: 'MARGINAL',
      status: 'open',
      openedAt: '2026-07-03T11:00:00Z',
      owner: '@error-book-pm',
    },
    {
      badcaseId: 'bc-2026-07-002',
      featureArea: 'resume_optimize',
      evalVerdict: 'REGRESS',
      status: 'regressing',
      openedAt: '2026-07-02T10:00:00Z',
      owner: '@resume-pm',
    },
    {
      badcaseId: 'bc-2026-07-001',
      featureArea: 'mock_interview',
      evalVerdict: 'FAIL',
      status: 'reviewing',
      openedAt: '2026-07-02T10:00:00Z',
      owner: '@ai-pm',
    },
  ],
  freshnessAt: '2026-07-04T10:00:00Z',
}

describe('REQ-044 US3 / FR-016 + AC-16.1 KPITiles', () => {
  it('renders 4 KPI tiles', () => {
    render(<KPITiles kpis={sampleKpis} />)
    expect(screen.getByTestId('kpi-tile-total-volume')).toBeInTheDocument()
    expect(screen.getByTestId('kpi-tile-success-rate')).toBeInTheDocument()
    expect(screen.getByTestId('kpi-tile-p95-latency')).toBeInTheDocument()
    expect(screen.getByTestId('kpi-tile-total-cost')).toBeInTheDocument()
  })

  it('EC-1: zero AI tasks surfaces the "0 AI tasks" banner', () => {
    const zeroKpis: KPIBundle = { ...sampleKpis, totalVolume: 0, freshnessAt: 'unknown' }
    render(<KPITiles kpis={zeroKpis} />)
    expect(screen.getByTestId('ai-operations-zero-banner')).toBeInTheDocument()
    expect(
      screen.getAllByTestId('kpi-freshness-stale').length,
    ).toBeGreaterThanOrEqual(1)
  })
})

describe('REQ-044 US3 / FR-016 + AC-16.2 VolumeByFeatureChart', () => {
  it('renders 4 area rows', () => {
    render(
      <VolumeByFeatureChart
        rows={[
          { featureArea: 'resume_optimize', callCount: 1284, successCount: 1181, failureCount: 103 },
          { featureArea: 'mock_interview', callCount: 723, successCount: 622, failureCount: 101 },
          { featureArea: 'error_coach', callCount: 512, successCount: 399, failureCount: 113 },
          { featureArea: 'resume_render', callCount: 142, successCount: 135, failureCount: 7 },
        ]}
        versionSelector={sampleVersions}
      />,
    )
    expect(screen.getByTestId('volume-row-resume_optimize')).toBeInTheDocument()
    expect(screen.getByTestId('volume-row-mock_interview')).toBeInTheDocument()
    expect(screen.getByTestId('volume-row-error_coach')).toBeInTheDocument()
    expect(screen.getByTestId('volume-row-resume_render')).toBeInTheDocument()
    expect(screen.getByTestId('chart-baseline-label').textContent).toMatch(
      /last 7 days/,
    )
  })
})

describe('REQ-044 US3 / FR-016 + AC-16.3 FailureCategoriesPie', () => {
  it('renders 5 failure category rows', () => {
    render(
      <FailureCategoriesPie
        rows={[
          { category: 'timeout', count: 96, share: 0.296 },
          { category: 'token_limit', count: 38, share: 0.117 },
          { category: 'parse_error', count: 67, share: 0.207 },
          { category: 'eval_failed', count: 84, share: 0.259 },
          { category: 'api_5xx', count: 39, share: 0.120 },
        ]}
        versionSelector={sampleVersions}
      />,
    )
    for (const cat of ['timeout', 'token_limit', 'parse_error', 'eval_failed', 'api_5xx']) {
      expect(screen.getByTestId(`failure-row-${cat}`)).toBeInTheDocument()
    }
  })
})

describe('REQ-044 US3 / FR-016 + AC-16.4 LatencyBandsChart', () => {
  it('renders p50/p95/p99 columns + 4 area rows', () => {
    render(
      <LatencyBandsChart
        entries={[
          { featureArea: 'resume_optimize', p50LatencyMs: 1280, p95LatencyMs: 2420, p99LatencyMs: 4180 },
          { featureArea: 'mock_interview', p50LatencyMs: 1820, p95LatencyMs: 3120, p99LatencyMs: 5470 },
          { featureArea: 'error_coach', p50LatencyMs: 920, p95LatencyMs: 1640, p99LatencyMs: 2890 },
          { featureArea: 'resume_render', p50LatencyMs: 3210, p95LatencyMs: 5640, p99LatencyMs: 7980 },
        ]}
        versionSelector={sampleVersions}
      />,
    )
    expect(screen.getByTestId('latency-col-p50')).toBeInTheDocument()
    expect(screen.getByTestId('latency-col-p95')).toBeInTheDocument()
    expect(screen.getByTestId('latency-col-p99')).toBeInTheDocument()
    expect(screen.getByTestId('latency-p95-resume_optimize').textContent).toMatch(/2\.42s/)
  })
})

describe('REQ-044 US3 / FR-016 + AC-16.5 TokenUsageChart', () => {
  it('renders input vs output rows + token totals', () => {
    render(
      <TokenUsageChart
        rows={[
          {
            featureArea: 'resume_optimize',
            promptTokens: 2_842_000,
            completionTokens: 486_000,
            totalTokens: 3_328_000,
          },
          {
            featureArea: 'mock_interview',
            promptTokens: 4_215_000,
            completionTokens: 812_000,
            totalTokens: 5_027_000,
          },
        ]}
        versionSelector={sampleVersions}
      />,
    )
    expect(screen.getByTestId('token-row-resume_optimize')).toBeInTheDocument()
    expect(screen.getByTestId('token-input-resume_optimize')).toBeInTheDocument()
    expect(screen.getByTestId('token-output-resume_optimize')).toBeInTheDocument()
  })
})

describe('REQ-044 US3 / FR-016 + AC-16.6 + EC-3 CostSummaryCard', () => {
  it('renders total + breakdown', () => {
    render(
      <CostSummaryCard
        summary={{
          totalCostUsd: 2.4842,
          byFeature: [
            { featureArea: 'resume_optimize', costUsd: 0.7179, share: 0.289 },
            { featureArea: 'mock_interview', costUsd: 1.1195, share: 0.451 },
            { featureArea: 'error_coach', costUsd: 0.438, share: 0.176 },
            { featureArea: 'resume_render', costUsd: 0.2088, share: 0.084 },
          ],
          lastReconciledAt: '2026-06-27T10:00:00Z',
          isEstimate: true,
          stale: false,
          freshnessAt: '2026-07-04T10:00:00Z',
        }}
      />,
    )
    expect(screen.getByTestId('cost-total').textContent).toMatch(/2\.4842/)
    expect(screen.getByTestId('cost-row-mock_interview')).toBeInTheDocument()
    expect(screen.queryByTestId('cost-stale-warning')).toBeNull()
  })

  it('EC-3: stale flag renders "cost estimate outdated" warning', () => {
    render(
      <CostSummaryCard
        summary={{
          totalCostUsd: 2.4842,
          byFeature: [],
          lastReconciledAt: '2026-06-01T10:00:00Z',
          isEstimate: true,
          stale: true,
          freshnessAt: '2026-07-04T10:00:00Z',
        }}
      />,
    )
    expect(screen.getByTestId('cost-stale-warning').textContent).toMatch(
      /cost estimate outdated/,
    )
  })
})

describe('REQ-044 US3 / FR-017 + AC-17.1 + EC-2 VersionSelector', () => {
  it('renders all 4 version dimensions', () => {
    render(<VersionSelector data={sampleVersions} onChange={vi.fn()} />)
    expect(screen.getByTestId('version-dim-prompt_fingerprint')).toBeInTheDocument()
    expect(screen.getByTestId('version-dim-rubric_version')).toBeInTheDocument()
    expect(screen.getByTestId('version-dim-model')).toBeInTheDocument()
    expect(screen.getByTestId('version-dim-app_version')).toBeInTheDocument()
  })

  it('EC-2: surfaces "version unknown" warning for legacy rows', () => {
    render(<VersionSelector data={sampleVersions} onChange={vi.fn()} />)
    expect(screen.getByTestId('version-unknown-prompt_fingerprint')).toBeInTheDocument()
    expect(screen.getByTestId('version-unknown-rubric_version').textContent).toMatch(
      /version unknown/,
    )
  })

  it('AC-17.4: changing a dimension invokes onChange with a non-baseline value', () => {
    const onChange = vi.fn()
    render(<VersionSelector data={sampleVersions} onChange={onChange} />)
    fireEvent.change(screen.getByTestId('version-select-model'), {
      target: { value: 'deepseek-chat' },
    })
    expect(onChange).toHaveBeenCalled()
    const lastArgs = onChange.mock.calls.at(-1)?.[0] as Record<string, string>
    expect(lastArgs.model).toBe('deepseek-chat')
  })

  it('AC-17.2: feature_area multi-select surfaces all 4 chips', () => {
    render(<VersionSelector data={sampleVersions} onChange={vi.fn()} />)
    expect(screen.getByTestId('feature-area-chip-resume_optimize')).toBeInTheDocument()
    expect(screen.getByTestId('feature-area-chip-mock_interview')).toBeInTheDocument()
    expect(screen.getByTestId('feature-area-chip-error_coach')).toBeInTheDocument()
    expect(screen.getByTestId('feature-area-chip-resume_render')).toBeInTheDocument()
  })
})

describe('REQ-044 US3 / FR-018 + AC-18.2 QualityIssueDrawer', () => {
  it('renders all 8 FR-018 link fields', () => {
    render(
      <QualityIssueDrawer issue={sampleIssue} onClose={vi.fn()} open={true} />,
    )
    for (const field of [
      'eval-verdict',
      'badcase-id',
      'affected-feature-area',
      'affected-journey-step',
      'owner',
      'status',
      'recommended-action',
      'feature-area-dimension',
    ]) {
      expect(screen.getByTestId(`drawer-field-${field}`)).toBeInTheDocument()
    }
  })

  it('AC-18.3: "View badcase" button is rendered with deep-link href', () => {
    render(
      <QualityIssueDrawer issue={sampleIssue} onClose={vi.fn()} open={true} />,
    )
    const link = screen.getByTestId('drawer-view-badcase')
    expect(link).toBeInTheDocument()
    expect(link.getAttribute('href')).toMatch(/incidents-badcases\?from=bc-2026-07-001/)
  })

  it('renders empty placeholder when closed', () => {
    const { container } = render(
      <QualityIssueDrawer issue={sampleIssue} onClose={vi.fn()} open={false} />,
    )
    expect(
      container.querySelector('[data-testid="ai-operations-quality-drawer-closed"]'),
    ).toBeTruthy()
  })
})

describe('REQ-044 US3 / FR-019 + AC-19.2/19.3 CostQualityAlert', () => {
  const criticalFlag: CostQualityFlag = {
    flagged: true,
    severity: 'critical',
    costDeltaPct: 0.18,
    qualityDeltaPct: -0.07,
    costPerQualityDeltaUsd: 5.143,
    message: '近 7 天成本上升 18% 同时质量下降 7%，触发成本-质量脱钩告警',
    linkedModel: 'gpt-4o-mini',
    linkedPrompt: 'prompt-v3.2',
    linkedFeatureArea: 'resume_optimize',
    linkedCohort: 'cohort-active',
    windowStart: '2026-06-27T10:00:00Z',
    windowEnd: '2026-07-04T10:00:00Z',
  }

  it('renders the alert with severity + linked model/prompt/feature/cohort', () => {
    render(
      <CostQualityAlert
        flag={criticalFlag}
        onOpenQualityIssue={vi.fn()}
        fallbackIssue={sampleIssue}
      />,
    )
    expect(screen.getByTestId('cost-quality-alert')).toBeInTheDocument()
    expect(screen.getByTestId('alert-severity').textContent).toMatch(/CRITICAL/)
    expect(screen.getByTestId('alert-linked-model').textContent).toBe('gpt-4o-mini')
    expect(screen.getByTestId('alert-linked-prompt').textContent).toBe('prompt-v3.2')
    expect(screen.getByTestId('alert-linked-feature').textContent).toBe('resume_optimize')
    expect(screen.getByTestId('alert-linked-cohort').textContent).toBe('cohort-active')
  })

  it('AC-19.3: clicking the alert invokes onOpenQualityIssue with the fallback', () => {
    const onOpen = vi.fn()
    render(
      <CostQualityAlert
        flag={criticalFlag}
        onOpenQualityIssue={onOpen}
        fallbackIssue={sampleIssue}
      />,
    )
    fireEvent.click(screen.getByTestId('cost-quality-alert'))
    expect(onOpen).toHaveBeenCalledWith(sampleIssue)
  })

  it('does not render when flag.flagged=false', () => {
    const { container } = render(
      <CostQualityAlert
        flag={{ ...criticalFlag, flagged: false }}
        onOpenQualityIssue={vi.fn()}
      />,
    )
    expect(container.firstChild).toBeNull()
  })
})

describe('REQ-044 US3 / FR-020 + AC-20.1/20.2 EvalBadcaseSummaryCard', () => {
  it('renders eval totals + pass rate + open badcases count', () => {
    render(
      <EvalBadcaseSummaryCard summary={sampleEvalSummary} onViewInLogs={vi.fn()} />,
    )
    expect(screen.getByTestId('eval-total-runs').textContent).toMatch(/187/)
    expect(screen.getByTestId('eval-pass-rate').textContent).toMatch(/83\.4%/)
    expect(screen.getByTestId('open-badcases-count').textContent).toMatch(/1/)
  })

  it('AC-20.2: renders 5 recent badcase rows (sliced from seed of 6)', () => {
    render(
      <EvalBadcaseSummaryCard summary={sampleEvalSummary} onViewInLogs={vi.fn()} />,
    )
    // The card renders the 5 most-recent rows (slice 0..5). bc-2026-07-006
    // (newest) is rendered; bc-2026-07-001 (oldest) is overflow + not rendered.
    expect(screen.getByTestId('recent-badcase-bc-2026-07-006')).toBeInTheDocument()
    expect(
      screen.queryByTestId('recent-badcase-bc-2026-07-001'),
    ).not.toBeInTheDocument()
  })

  it('AC-20.3: "View in Logs" button invokes the prop handler', () => {
    const onView = vi.fn()
    render(
      <EvalBadcaseSummaryCard summary={sampleEvalSummary} onViewInLogs={onView} />,
    )
    fireEvent.click(screen.getByTestId('view-in-logs-button'))
    expect(onView).toHaveBeenCalledOnce()
  })
})

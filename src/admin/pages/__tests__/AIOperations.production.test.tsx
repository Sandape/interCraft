/**
 * REQ-061 US9 / T114 — production AI Operations frontend expectations.
 *
 * Requires real data_quality, explicit unknowns, beta revenue zero,
 * stable filters, and point→milestone→attempt→cost drilldown surfaces.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AIOperations } from '../AIOperations'
import { AICostDrilldown } from '@/admin/components/ai-operations/AICostDrilldown'
import { PointCostTimeline } from '@/admin/components/ai-operations/PointCostTimeline'
import type { MetricsResponse, TaskCostDrilldown } from '@/admin/api/ai-operations'

const metricsFixture: MetricsResponse = {
  stability: { success_rate: 0.92 },
  quality: { badcase_rate: 0.01 },
  latency: { p95_ms: 1200 },
  points: { settled_total: 42 },
  cost: { rmb_total: '12.34', unknown_cost_events: 1 },
  revenue_rmb: { amount: '0', currency: 'CNY' },
  data_quality: {
    fresh_at: '2026-07-11T10:00:00Z',
    coverage_percent: 97.5,
    unknown_count: 3,
    seed_or_mock_count: 0,
  },
}

const drilldownFixture: TaskCostDrilldown = {
  task_id: '00000000-0000-7000-8000-000000000061',
  point_settled: 8,
  cost_status: 'mixed',
  current_cost_rmb: { amount: '1.23', currency: 'CNY' },
  attempts: [
    {
      attempt_id: 'att-1',
      attempt_kind: 'model',
      cost_status: 'provider_confirmed',
      cost: { amount: '1.00', currency: 'CNY' },
      cost_rate_version: 'rate-v1',
      adjustment: '0.00',
    },
  ],
  milestones: [
    {
      milestone: 'accepted',
      occurred_at: '2026-07-11T09:00:00Z',
      points: 8,
      cost_rmb: '0',
    },
    {
      milestone: 'settled',
      occurred_at: '2026-07-11T09:01:00Z',
      points: null,
      cost_rmb: null,
    },
  ],
  data_quality: {
    fresh_at: '2026-07-11T10:00:00Z',
    coverage_percent: 100,
    unknown_count: 2,
    seed_or_mock_count: 0,
  },
}

vi.mock('@/admin/hooks/queries/useAIOperations', async () => {
  const actual = await vi.importActual<
    typeof import('@/admin/hooks/queries/useAIOperations')
  >('@/admin/hooks/queries/useAIOperations')
  return {
    ...actual,
    useProductionMetrics: () => ({
      isLoading: false,
      isError: false,
      data: metricsFixture,
    }),
    useProductionBudgets: () => ({
      isLoading: false,
      isError: false,
      data: {
        items: [
          {
            budget_id: 'site:*:day',
            scope_type: 'site',
            scope_ref: '*',
            period: 'day',
            amount_rmb: { amount: '1000', currency: 'CNY' },
            consumed_rmb: { amount: '0', currency: 'CNY' },
            utilization_percent: '0',
            level: 'ok',
            warning_reached: false,
            hard_limit_reached: false,
            stop_new_optional_tasks: false,
          },
        ],
      },
    }),
    useProductionReconciliations: () => ({
      isLoading: false,
      isError: false,
      data: { items: [] },
    }),
    useProductionAnomalies: () => ({
      isLoading: false,
      isError: false,
      data: {
        items: [],
        protected_operations: ['query', 'cancel', 'appeal'],
      },
    }),
    useTaskCostDrilldown: (taskId: string | null) => ({
      isLoading: false,
      isError: false,
      data: taskId ? drilldownFixture : null,
    }),
    useKpis: () => ({ data: undefined }),
    useVolumeByFeature: () => ({ data: undefined }),
    useFailureCategories: () => ({ data: undefined }),
    useLatencyBands: () => ({ data: undefined }),
    useTokenUsage: () => ({ data: undefined }),
    useCostSummary: () => ({ data: undefined }),
    useVersionSelector: () => ({ data: undefined }),
    useQualityIssues: () => ({ data: undefined }),
    useCostQualityFlag: () => ({ data: undefined }),
    useEvalBadcaseSummary: () => ({ data: undefined }),
  }
})

vi.mock('@/admin/hooks/queries/useProductAnalytics', () => ({
  useCohorts: () => ({
    isLoading: false,
    isError: false,
    data: { cohorts: [] },
  }),
}))

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AIOperations />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AIOperations production surface (T114)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders data quality with zero seed/mock and non-zero unknowns', () => {
    renderPage()
    const dq = screen.getByTestId('production-data-quality')
    expect(dq).toHaveAttribute('data-seed-or-mock', '0')
    expect(screen.getByTestId('production-unknown-count').textContent).toContain(
      '3',
    )
    expect(screen.getByTestId('production-seed-count').textContent).toContain(
      '0',
    )
  })

  it('keeps beta revenue at zero', () => {
    renderPage()
    expect(screen.getByTestId('beta-revenue-amount').textContent).toMatch(
      /^0\s+CNY$/,
    )
  })

  it('applies filters through stable form controls', async () => {
    renderPage()
    fireEvent.change(screen.getByTestId('filter-capability'), {
      target: { value: 'interview' },
    })
    fireEvent.change(screen.getByTestId('filter-service-tier'), {
      target: { value: 'quality' },
    })
    fireEvent.click(screen.getByTestId('filter-apply'))
    expect(screen.getByTestId('filter-capability')).toHaveValue('interview')
    expect(screen.getByTestId('filter-service-tier')).toHaveValue('quality')
  })

  it('opens point→milestone→attempt→cost drilldown', async () => {
    renderPage()
    fireEvent.click(screen.getByTestId('open-cost-drilldown'))
    await waitFor(() => {
      expect(screen.getByTestId('ai-cost-drilldown')).toBeInTheDocument()
    })
    expect(screen.getByTestId('point-cost-timeline')).toBeInTheDocument()
    expect(screen.getByTestId('drilldown-task-id').textContent).toContain(
      '00000000-0000-7000-8000-000000000061',
    )
    expect(screen.getByTestId('drilldown-attempt-0')).toBeInTheDocument()
    expect(screen.getByTestId('point-cost-milestone-1')).toHaveAttribute(
      'data-points',
      'unknown',
    )
  })

  it('AICostDrilldown surfaces rate and adjustment fields', () => {
    render(
      <AICostDrilldown
        open
        drilldown={drilldownFixture}
        onClose={() => undefined}
      />,
    )
    expect(screen.getByTestId('drilldown-rate-0').textContent).toContain(
      'rate-v1',
    )
    expect(screen.getByTestId('drilldown-adjustment-0').textContent).toContain(
      '0.00',
    )
  })

  it('PointCostTimeline marks unavailable and unknown points', () => {
    const { rerender } = render(
      <PointCostTimeline milestones={[]} unavailable />,
    )
    expect(
      screen.getByTestId('point-cost-timeline-unavailable'),
    ).toBeInTheDocument()

    rerender(
      <PointCostTimeline
        milestones={[{ milestone: 'x', points: null, cost_rmb: null }]}
      />,
    )
    expect(screen.getByTestId('point-cost-milestone-0')).toHaveAttribute(
      'data-cost',
      'unknown',
    )
  })
})

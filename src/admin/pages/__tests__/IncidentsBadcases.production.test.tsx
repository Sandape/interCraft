/**
 * REQ-061 T129 — production Bad Case workspace frontend tests.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { BadcaseList } from '@/admin/components/incidents/BadcaseList'
import { BadcaseDrawer } from '@/admin/components/incidents/BadcaseDrawer'
import type { OperationalBadcaseSummary } from '@/admin/api/badcases-production'

const sample: OperationalBadcaseSummary = {
  badcase_id: 'badcase-1',
  status: 'OPEN',
  severity: 'P1',
  category: 'fact_error',
  capabilities: ['resume_derive'],
  owner: null,
  privacy_class: 'metadata',
  first_seen_at: '2026-07-11T00:00:00Z',
  last_seen_at: '2026-07-11T01:00:00Z',
  task_count: 2,
  user_count: null,
  user_count_status: 'unknown',
  point_treatment_status: 'pending',
  sla_status: 'at_risk',
  version: 1,
  data_completeness: 'partial',
}

const getMock = vi.fn()
const impactsMock = vi.fn()
const actionMock = vi.fn()

vi.mock('@/admin/api/badcases-production', async () => {
  const actual = await vi.importActual<typeof import('@/admin/api/badcases-production')>(
    '@/admin/api/badcases-production',
  )
  return {
    ...actual,
    productionBadcasesApi: {
      list: vi.fn(),
      get: (...args: unknown[]) => getMock(...args),
      timeline: vi.fn().mockResolvedValue({
        items: [],
        data_quality: { seed_or_mock_count: 0 },
      }),
      impacts: (...args: unknown[]) => impactsMock(...args),
      action: (...args: unknown[]) => actionMock(...args),
    },
  }
})

vi.mock('@/admin/hooks/queries/useIncidents', () => ({
  useEscalateBadcase: () => ({ mutateAsync: vi.fn() }),
}))

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('IncidentsBadcases.production', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getMock.mockResolvedValue({
      badcase: sample,
      user_visible_status: '已提交',
    })
    impactsMock.mockResolvedValue({
      items: [
        {
          impact_id: 'i1',
          impact_kind: 'task',
          subject_ref: 't1',
          confidence: 'confirmed',
          first_seen_at: null,
          last_updated_at: null,
          evidence_refs: [],
          version: 1,
        },
        {
          impact_id: 'i2',
          impact_kind: 'user',
          subject_ref: 'u1',
          confidence: 'unknown',
          first_seen_at: null,
          last_updated_at: null,
          evidence_refs: [],
          version: 1,
        },
      ],
      data_quality: { seed_or_mock_count: 0, unknown_count: 1 },
    })
    actionMock.mockRejectedValue(new Error('CLOSURE_EVIDENCE_REQUIRED'))
  })

  it('lists operational badcases with filters and data quality', () => {
    wrap(
      <BadcaseList
        items={[{ kind: 'operational', value: sample }]}
        onOpen={() => undefined}
        filters={{ severity: 'P1' }}
        dataQuality={{
          fresh_at: '2026-07-11T02:00:00Z',
          unknown_count: 1,
          seed_or_mock_count: 0,
        }}
      />,
    )
    expect(screen.getByTestId('badcase-list')).toBeInTheDocument()
    expect(screen.getByTestId('badcase-card-badcase-1')).toHaveAttribute(
      'data-severity',
      'P1',
    )
    expect(screen.getByTestId('dq-seed-count')).toHaveTextContent('seed=0')
    expect(screen.getByTestId('sla-status')).toHaveTextContent('at_risk')
  })

  it('shows unavailable instead of seed fallback', () => {
    wrap(
      <BadcaseList
        items={[]}
        onOpen={() => undefined}
        unavailable
        dataQuality={{ fresh_at: '2026-07-10T00:00:00Z', seed_or_mock_count: 0 }}
      />,
    )
    expect(screen.getByTestId('badcase-list-unavailable')).toBeInTheDocument()
    expect(screen.getByTestId('badcase-fresh-at')).toHaveTextContent('2026-07-10')
  })

  it('drawer exposes impact confidence filters and typed action closure gate', async () => {
    wrap(
      <BadcaseDrawer
        item={{ kind: 'operational', value: sample }}
        onClose={() => undefined}
        canEscalate={false}
        canManage
      />,
    )

    fireEvent.click(screen.getByTestId('badcase-tab-impacts'))
    await waitFor(() => {
      expect(screen.getByTestId('impact-list')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('impact-filter-unknown'))
    expect(screen.getByTestId('impact-i2')).toHaveAttribute(
      'data-confidence',
      'unknown',
    )

    fireEvent.click(screen.getByTestId('badcase-tab-actions'))
    fireEvent.click(screen.getByTestId('action-close'))
    await waitFor(() => {
      expect(screen.getByTestId('action-error')).toHaveTextContent(
        'CLOSURE_EVIDENCE_REQUIRED',
      )
    })
  })

  it('overview shows version and status tabs', () => {
    wrap(
      <BadcaseDrawer
        item={{ kind: 'operational', value: sample }}
        onClose={() => undefined}
        canEscalate={false}
        canManage
      />,
    )
    expect(screen.getByTestId('badcase-tab-overview')).toBeInTheDocument()
    expect(screen.getByTestId('overview-status')).toHaveTextContent('OPEN')
    expect(screen.getByTestId('overview-version')).toHaveTextContent('1')
    expect(screen.getByTestId('drawer-severity')).toHaveTextContent('P1')
  })
})

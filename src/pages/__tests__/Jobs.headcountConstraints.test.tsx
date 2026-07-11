/* 020 (FIX-010, D-017) — headcount input must have HTML hard
   constraints (type="number", min="1", step="1").

Round-1 evidence: the Input was a plain text field with a JS-side
`replace(/[^0-9]/g, '')`. Non-digit keystrokes were stripped, but
negative numbers, zero, decimals, and E2E auto-fill bypasses were all
possible. Mobile keyboards also wouldn't show the numeric keypad.

The fix: add the standard HTML attributes so the browser enforces the
constraints natively in addition to the JS guard.
*/
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Jobs from '@/pages/Jobs'
import type { Job } from '@/repositories/JobRepository'

vi.mock('@/hooks/queries/useJobs', () => ({
  useJobs: () => ({
    data: { data: [], next_cursor: null, has_more: false },
    isLoading: false,
  }),
  useJobStats: () => ({ data: { counts: { all: 0 }, total: 0 }, isLoading: false }),
}))

vi.mock('@/hooks/queries/useJobTransitions', () => ({
  useJobTransitions: () => ({
    data: {
      statuses: ['applied', 'test', 'oa', 'hr', 'offer', 'rejected', 'withdrawn'],
      transitions: [{ from: 'applied', to: 'test' }],
    },
    isStale: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('@/hooks/mutations/useJobMutations', () => ({
  useCreateJob: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateJobStatus: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteJob: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/hooks/queries/useInterviewSessions', () => ({
  useCreateInterviewFromJob: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/components/lock/OfflineBanner', () => ({ OfflineBanner: () => null }))

const baseJob: Job = {
  id: 'job-1',
  company: '字节',
  position: '前端',
  jd_url: null,
  branch_id: null,
  status: 'applied',
  interview_time: null,
  status_history: [],
  notes_md: null,
  base_location: '北京',
  requirements_md: null,
  employment_type: 'experienced',
  salary_range_text: null,
  headcount: 5,
  created_at: '2026-06-17T00:00:00Z',
  updated_at: '2026-06-17T00:00:00Z',
}

function renderJobs() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Jobs />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Jobs create modal — headcount HTML constraints (020 D-017)', () => {
  it('opens the create modal when the 添加职位 button is clicked', () => {
    renderJobs()
    fireEvent.click(screen.getByRole('button', { name: /添加职位/ }))
    expect(screen.getByTestId('job-create-headcount')).toBeInTheDocument()
  })

  it('exposes the required company and position inputs by their visible labels', () => {
    renderJobs()
    fireEvent.click(screen.getByRole('button', { name: /添加职位/ }))

    expect(screen.getByLabelText('公司 *')).toHaveAttribute('data-testid', 'job-create-company')
    expect(screen.getByLabelText('岗位 *')).toHaveAttribute('data-testid', 'job-create-position')
  })

  it('headcount input has type="number"', () => {
    renderJobs()
    fireEvent.click(screen.getByRole('button', { name: /添加职位/ }))
    const input = screen.getByTestId('job-create-headcount')
    expect(input).toHaveAttribute('type', 'number')
  })

  it('headcount input has min="1"', () => {
    renderJobs()
    fireEvent.click(screen.getByRole('button', { name: /添加职位/ }))
    const input = screen.getByTestId('job-create-headcount')
    expect(input).toHaveAttribute('min', '1')
  })

  it('headcount input has step="1"', () => {
    renderJobs()
    fireEvent.click(screen.getByRole('button', { name: /添加职位/ }))
    const input = screen.getByTestId('job-create-headcount')
    expect(input).toHaveAttribute('step', '1')
  })

  it('headcount input still keeps inputMode="numeric" for mobile keyboards', () => {
    renderJobs()
    fireEvent.click(screen.getByRole('button', { name: /添加职位/ }))
    const input = screen.getByTestId('job-create-headcount')
    expect(input).toHaveAttribute('inputmode', 'numeric')
  })

  it('rejects negative values via min=1 HTML constraint (browser-level)', () => {
    renderJobs()
    fireEvent.click(screen.getByRole('button', { name: /添加职位/ }))
    const input = screen.getByTestId('job-create-headcount') as HTMLInputElement
    // The browser-level validity API reflects the min attribute.
    input.value = '0'
    expect(input.checkValidity()).toBe(false)
    input.value = '-3'
    expect(input.checkValidity()).toBe(false)
    input.value = '5'
    expect(input.checkValidity()).toBe(true)
  })
})

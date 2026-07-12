import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Jobs from '@/pages/Jobs'
import type { Job } from '@/repositories/JobRepository'

const useJobsMock = vi.fn()

vi.mock('@/hooks/queries/useJobs', () => ({
  useJobs: (params: unknown) => useJobsMock(params),
  useJobStats: () => ({ data: { counts: { applied: 1 }, total: 1 }, isLoading: false }),
}))

vi.mock('@/hooks/queries/useJobTransitions', () => ({
  useJobTransitions: () => ({
    data: {
      statuses: ['applied', 'test', 'interview_1', 'passed', 'failed'],
      transitions: [],
    },
    isStale: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('@/hooks/mutations/useJobMutations', () => ({
  useCreateJob: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateJobStatus: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteJob: () => ({ mutate: vi.fn(), isPending: false }),
  useBindBranchToJob: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/hooks/queries/useInterviewSessions', () => ({
  useCreateInterviewFromJob: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/components/lock/OfflineBanner', () => ({ OfflineBanner: () => null }))

const job: Job = {
  id: 'job-deep-link',
  company: '星河科技',
  position: '产品经理',
  jd_url: null,
  branch_id: null,
  status: 'applied',
  interview_time: '2026-07-11T18:00:00Z',
  status_history: [],
  notes_md: null,
  base_location: '上海',
  requirements_md: null,
  employment_type: 'experienced',
  salary_range_text: null,
  headcount: 1,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

function withJob(overrides: Partial<Job>): Job {
  return { ...job, ...overrides }
}

function renderJobs(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[path]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/jobs/:jobId" element={<Jobs />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  useJobsMock.mockReturnValue({
    data: { data: [job], next_cursor: null, has_more: false },
    isLoading: false,
  })
})

describe('Jobs URL state', () => {
  it('opens the matching job detail from a /jobs/:jobId deep link', () => {
    renderJobs('/jobs/job-deep-link')

    expect(screen.getByTestId('job-detail-panel')).toBeInTheDocument()
  })

  it('uses ?status= as the initial jobs filter', () => {
    renderJobs('/jobs?status=applied')

    expect(useJobsMock).toHaveBeenCalledWith({ status: 'applied' })
    expect(screen.getByRole('tab', { name: /已投递/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('opens the existing create modal from ?new=true', () => {
    renderJobs('/jobs?new=true')

    expect(screen.getByRole('dialog', { name: '添加职位' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(screen.queryByRole('dialog', { name: '添加职位' })).not.toBeInTheDocument()
  })

  it('filters the interviewing funnel view to interview statuses', () => {
    useJobsMock.mockReturnValue({
      data: {
        data: [
          withJob({ id: 'applied', company: '投递公司', status: 'applied' }),
          withJob({ id: 'interview', company: '面试公司', status: 'interview_2' }),
        ],
        next_cursor: null,
        has_more: false,
      },
      isLoading: false,
    })

    renderJobs('/jobs?view=interviewing')

    expect(screen.getByText('面试公司')).toBeInTheDocument()
    expect(screen.queryByText('投递公司')).not.toBeInTheDocument()
  })

  it('filters awaiting feedback to past interview appointments', () => {
    const past = new Date(Date.now() - 60 * 60 * 1000).toISOString()
    const future = new Date(Date.now() + 60 * 60 * 1000).toISOString()
    useJobsMock.mockReturnValue({
      data: {
        data: [
          withJob({ id: 'past', company: '待反馈公司', status: 'interview_1', interview_time: past }),
          withJob({ id: 'future', company: '待面试公司', status: 'interview_1', interview_time: future }),
        ],
        next_cursor: null,
        has_more: false,
      },
      isLoading: false,
    })

    renderJobs('/jobs?view=awaiting_feedback')

    expect(screen.getByText('待反馈公司')).toBeInTheDocument()
    expect(screen.queryByText('待面试公司')).not.toBeInTheDocument()
  })

  it('filters the today-interview entry without losing all jobs data', () => {
    const today = new Date()
    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)
    useJobsMock.mockReturnValue({
      data: {
        data: [
          withJob({ id: 'today', company: '今日公司', interview_time: today.toISOString() }),
          withJob({ id: 'tomorrow', company: '明日公司', interview_time: tomorrow.toISOString() }),
        ],
        next_cursor: null,
        has_more: false,
      },
      isLoading: false,
    })

    renderJobs('/jobs?interview=today')

    expect(screen.getByText('今日公司')).toBeInTheDocument()
    expect(screen.queryByText('明日公司')).not.toBeInTheDocument()
  })
})

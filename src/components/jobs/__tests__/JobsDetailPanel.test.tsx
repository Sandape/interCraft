/** 019 — JobsDetailPanel CTAs: resume branch creation + interview start (mutation flow). */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createElement, type ReactNode } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { JobsDetailPanel } from '@/components/jobs/JobsDetailPanel'
import type { Job } from '@/repositories/JobRepository'

// REQ-053 (T068) — the panel calls useQueryClient() to invalidate the
// report cache, so wrap every render in a fresh QueryClient.
function wrap(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

// REQ-053 (T068) — the panel now queries research reports to decide whether
// to surface the "查看备战报告" entry. Default to no reports so the existing
// 019 assertions still pass; the dedicated research-report test overrides
// this via `vi.mocked(...).mockReturnValueOnce(...)`.
vi.mock('@/hooks/queries/useResearchReports', () => ({
  useResearchReports: () => ({ data: { data: [] }, isLoading: false }),
}))

vi.mock('@/modules/resume/derive/api', () => ({
  listJobDerivedResumes: vi.fn(() => new Promise(() => undefined)),
}))

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
  requirements_md: '## 要求\n- 3年 React 经验',
  employment_type: 'experienced',
  salary_range_text: '30-50K · 16薪',
  headcount: 5,
  created_at: '2026-06-17T00:00:00Z',
  updated_at: '2026-06-17T00:00:00Z',
}

beforeEach(() => {
  mockNavigate.mockReset()
})

describe('JobsDetailPanel — CTAs (019)', () => {
  it('shows resume-branch CTA and binds nothing yet', () => {
    wrap(<JobsDetailPanel job={baseJob} />)
    const cta = screen.getByTestId('job-detail-resume-cta')
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveTextContent('为该岗位创建简历分支')
    expect(screen.queryByTestId('job-detail-bound-branch')).not.toBeInTheDocument()
  })

  it('resume CTA navigates to /resume?new=true&source_job_id={id}', () => {
    wrap(<JobsDetailPanel job={baseJob} />)
    fireEvent.click(screen.getByTestId('job-detail-resume-cta'))
    expect(mockNavigate).toHaveBeenCalledWith('/resume?new=true&source_job_id=job-1')
  })

  it('interview CTA is disabled and shows hint when branch not bound', () => {
    wrap(<JobsDetailPanel job={baseJob} />)
    const cta = screen.getByTestId('job-detail-interview-cta')
    expect(cta).toBeDisabled()
    expect(screen.getByTestId('job-detail-interview-cta-hint')).toHaveTextContent('请先绑定简历分支')
  })

  it('interview CTA navigates to mode workbench with job_id and branch_id', async () => {
    const jobWithBranch: Job = { ...baseJob, branch_id: 'branch-9' }
    wrap(<JobsDetailPanel job={jobWithBranch} />)
    const cta = screen.getByTestId('job-detail-interview-cta')
    expect(cta).not.toBeDisabled()
    fireEvent.click(cta)

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        '/interview/mode?job_id=job-1&branch_id=branch-9',
      )
    })
  })

  it('shows the bound-branch link that navigates to /resume/{branch_id}', () => {
    const jobWithBranch: Job = { ...baseJob, branch_id: 'branch-9' }
    wrap(<JobsDetailPanel job={jobWithBranch} />)
    const link = screen.getByTestId('job-detail-bound-branch')
    expect(link).toBeInTheDocument()
    fireEvent.click(link)
    expect(mockNavigate).toHaveBeenCalledWith('/resume/branch-9')
  })

  it('hides the resume CTA once a branch is bound', () => {
    const jobWithBranch: Job = { ...baseJob, branch_id: 'branch-9' }
    wrap(<JobsDetailPanel job={jobWithBranch} />)
    expect(screen.queryByTestId('job-detail-resume-cta')).not.toBeInTheDocument()
  })
})

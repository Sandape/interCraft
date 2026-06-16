/** 019 — JobsDetailPanel CTAs: resume branch creation + interview start. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { JobsDetailPanel } from '@/components/jobs/JobsDetailPanel'
import type { Job } from '@/repositories/JobRepository'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const baseJob: Job = {
  id: 'job-1',
  company: '字节',
  position: '前端',
  jd_url: null,
  branch_id: null,
  status: 'applied',
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
    render(<MemoryRouter><JobsDetailPanel job={baseJob} /></MemoryRouter>)
    const cta = screen.getByTestId('job-detail-resume-cta')
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveTextContent('为该岗位创建简历分支')
    expect(screen.queryByTestId('job-detail-bound-branch')).not.toBeInTheDocument()
  })

  it('resume CTA navigates to /resume?new=true&source_job_id={id}', () => {
    render(<MemoryRouter><JobsDetailPanel job={baseJob} /></MemoryRouter>)
    fireEvent.click(screen.getByTestId('job-detail-resume-cta'))
    expect(mockNavigate).toHaveBeenCalledWith('/resume?new=true&source_job_id=job-1')
  })

  it('interview CTA is disabled and shows hint when branch not bound', () => {
    render(<MemoryRouter><JobsDetailPanel job={baseJob} /></MemoryRouter>)
    const cta = screen.getByTestId('job-detail-interview-cta')
    expect(cta).toBeDisabled()
    expect(screen.getByTestId('job-detail-interview-cta-hint')).toHaveTextContent('请先绑定简历分支')
  })

  it('interview CTA navigates to /interview?new=1&job_id=&branch_id= when branch bound', () => {
    const jobWithBranch: Job = { ...baseJob, branch_id: 'branch-9' }
    render(<MemoryRouter><JobsDetailPanel job={jobWithBranch} /></MemoryRouter>)
    const cta = screen.getByTestId('job-detail-interview-cta')
    expect(cta).not.toBeDisabled()
    fireEvent.click(cta)
    expect(mockNavigate).toHaveBeenCalledWith(
      '/interview?new=1&job_id=job-1&branch_id=branch-9',
    )
  })

  it('shows the bound-branch link that navigates to /resume/{branch_id}', () => {
    const jobWithBranch: Job = { ...baseJob, branch_id: 'branch-9' }
    render(<MemoryRouter><JobsDetailPanel job={jobWithBranch} /></MemoryRouter>)
    const link = screen.getByTestId('job-detail-bound-branch')
    expect(link).toBeInTheDocument()
    fireEvent.click(link)
    expect(mockNavigate).toHaveBeenCalledWith('/resume/branch-9')
  })

  it('hides the resume CTA once a branch is bound', () => {
    const jobWithBranch: Job = { ...baseJob, branch_id: 'branch-9' }
    render(<MemoryRouter><JobsDetailPanel job={jobWithBranch} /></MemoryRouter>)
    expect(screen.queryByTestId('job-detail-resume-cta')).not.toBeInTheDocument()
  })
})

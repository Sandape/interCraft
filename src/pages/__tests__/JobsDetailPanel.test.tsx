/** 019 — JobsDetailPanel (basic info card) renders the 5 extended fields with proper Chinese labels. */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { JobsDetailBasicInfo } from '@/pages/Jobs'
import type { Job } from '@/repositories/JobRepository'

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

describe('JobsDetailBasicInfo (019)', () => {
  it('renders 5 fields with proper Chinese labels', () => {
    render(<JobsDetailBasicInfo job={baseJob} />)
    expect(screen.getByTestId('job-detail-basic-info')).toBeInTheDocument()
    expect(screen.getByText('Base 地')).toBeInTheDocument()
    expect(screen.getByTestId('job-detail-base-location')).toHaveTextContent('北京')
    expect(screen.getByText(/招聘需求/)).toBeInTheDocument()
    expect(screen.getByText('岗位类型')).toBeInTheDocument()
    expect(screen.getByTestId('job-detail-employment-type')).toHaveTextContent('社招')
    expect(screen.getByText('薪资范围')).toBeInTheDocument()
    expect(screen.getByTestId('job-detail-salary')).toHaveTextContent('30-50K · 16薪')
    expect(screen.getByText('招聘人数')).toBeInTheDocument()
    expect(screen.getByTestId('job-detail-headcount')).toHaveTextContent('5')
  })

  it('renders default placeholders for empty / unspecified values', () => {
    const empty: Job = {
      ...baseJob,
      base_location: '',
      requirements_md: null,
      employment_type: 'unspecified',
      salary_range_text: null,
      headcount: null,
    }
    render(<JobsDetailBasicInfo job={empty} />)
    expect(screen.getByTestId('job-detail-base-location')).toHaveTextContent('未填写')
    expect(screen.getByTestId('job-detail-employment-type')).toHaveTextContent('未指定')
    expect(screen.getByTestId('job-detail-salary')).toHaveTextContent('未填写')
    expect(screen.getByTestId('job-detail-headcount')).toHaveTextContent('未填写')
  })

  it('requirements_md is a foldable card with markdown render', () => {
    render(<JobsDetailBasicInfo job={baseJob} />)
    const details = screen.getByTestId('job-detail-requirements')
    expect(details.tagName).toBe('DETAILS')
    expect(details.textContent).toContain('3年 React 经验')
  })
})

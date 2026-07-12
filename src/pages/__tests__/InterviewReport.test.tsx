/** 018 — defect #8 量纲统一 0-10。
 *  InterviewReport 总览卡必须显示 "X.X / 10" 与 "满分 10"，禁止 "满分 100"。
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('@/hooks/queries/useInterviewSessions', () => {
  const session = {
      id: 's-1',
      branch_id: null,
      job_id: null,
      position: 'Backend',
      company: 'ACME',
      mode: 'text',
      status: 'partially_succeeded',
      overall_score: 7.5,
      score: 7.5,
      duration_seconds: 600,
      max_questions: null,
      thread_id: null,
      started_at: null,
      ended_at: null,
      duration_sec: null,
      interview_plan: null,
      web_research: null,
      created_at: '2026-06-17T00:00:00Z',
      updated_at: '2026-06-17T00:00:00Z',
      // REQ-061 runtime projection — proved accessible below
      task_id: 'task-runtime-1',
      execution_id: null,
      available_actions: ['retry_failed_component'],
      points_summary: { settled: 5, reserved: 3 },
      milestones: [{ code: 'REPORT', status: 'completed', settle_eligible: true }],
      failure: { code: 'partial', message: '部分完成', safe: true },
  } satisfies import('@/repositories/interviewSessionRepo').InterviewSession

  return {
    useInterviewSession: vi.fn(() => ({ data: session, isLoading: false })),
  }
})

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query')
  return {
    ...actual,
    useQuery: () => ({
      data: {
        id: 'r-1',
        session_id: 's-1',
        overall_score: 7.5,
        dimension_scores: {},
        per_question_score: [],
        strengths: [],
        improvements: [],
        summary_md: '',
      },
      isLoading: false,
      error: null,
    }),
  }
})

function renderReport() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/interview/s-1/report']}>
        <Routes>
          <Route path="/interview/:id/report" element={<InterviewReport />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

import InterviewReport from '@/pages/InterviewReport'

describe('InterviewReport — 0-10 量纲 (018 #8)', () => {
  it('总览卡显示「满分 10」与 / 10', async () => {
    const { container } = renderReport()
    expect(await screen.findByText(/满分 10/)).toBeInTheDocument()
    const text = container.textContent ?? ''
    expect(text).toMatch(/\/ 10/)
    expect(text).toContain('7.5')
  })

  it('总览卡不出现「满分 100」', async () => {
    renderReport()
    expect(screen.queryByText(/满分 100/)).not.toBeInTheDocument()
  })

  it('REQ-061 runtime projection fields are accessible and render (type regression)', async () => {
    renderReport()
    // Task link renders
    expect(await screen.findByTestId('interview-report-task-link')).toBeInTheDocument()
    // Points summary renders
    expect(screen.getByTestId('interview-report-points')).toHaveTextContent(/5/)
    expect(screen.getByTestId('interview-report-points')).toHaveTextContent(/3/)
    // Milestones render
    expect(screen.getByTestId('interview-report-milestones')).toBeInTheDocument()
    expect(screen.getByTestId('interview-report-milestone-REPORT')).toBeInTheDocument()
    // Failure/partial alert renders
    expect(screen.getByTestId('interview-report-partial-or-failure')).toBeInTheDocument()
    expect(screen.getByTestId('interview-report-partial-or-failure')).toHaveTextContent(/部分完成/)
  })
})

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { InterviewModeSelect } from '../InterviewModeSelect'
import {
  __resetInterviewModeStoreForTests,
  useInterviewModeStore,
} from '@/stores/useInterviewModeStore'

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  jobs: [] as any[],
  resumes: [] as any[],
  useJobsParams: undefined as any,
  create: vi.fn(),
  start: vi.fn(),
  generatePlan: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  }
})

vi.mock('@/hooks/queries/useJobs', () => ({
  useJobs: (params: any) => {
    mocks.useJobsParams = params
    return {
    data: { data: mocks.jobs, next_cursor: null, has_more: false },
    isLoading: false,
    isError: false,
    }
  },
}))

vi.mock('@/hooks/queries/useResumeV2List', () => ({
  useResumeV2List: () => ({
    data: mocks.resumes,
    isLoading: false,
  }),
}))

vi.mock('@/repositories/interviewSessionRepo', () => ({
  interviewSessionRepo: {
    create: mocks.create,
    start: mocks.start,
    generatePlan: mocks.generatePlan,
  },
}))

const job = {
  id: 'job-1',
  company: 'Acme AI',
  position: 'AI Product Manager',
  jd_url: null,
  branch_id: null,
  status: 'interviewing',
  status_history: [],
  notes_md: null,
  base_location: 'Shanghai',
  requirements_md: 'Original JD: prompt design and AI product metrics.',
  employment_type: 'full_time',
  salary_range_text: '30k-50k',
  headcount: 1,
  created_at: '2026-07-07T00:00:00Z',
  updated_at: '2026-07-07T00:00:00Z',
}

const resume = {
  id: 'resume-1',
  name: 'AI PM Resume',
  slug: 'ai-pm',
  tags: [],
  is_public: false,
  is_locked: false,
  version: 1,
  created_at: null,
  updated_at: null,
}

function renderModeSelect(initialEntry = '/interview/mode') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/interview/mode" element={<InterviewModeSelect />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('InterviewModeSelect', () => {
  beforeEach(() => {
    __resetInterviewModeStoreForTests()
    mocks.navigate.mockReset()
    mocks.create.mockResolvedValue({ data: { id: 'session-1' } })
    mocks.start.mockResolvedValue({ data: { id: 'session-1', status: 'in_progress', started_at: 'now' } })
    mocks.generatePlan.mockResolvedValue({ data: { id: 'session-1', interview_plan: {}, web_research: {} } })
    mocks.jobs = [job]
    mocks.resumes = [resume]
    mocks.useJobsParams = undefined
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ data: { available: 0, required: 5 } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows an empty state and no manual target inputs when no jobs exist', async () => {
    mocks.jobs = []

    renderModeSelect()

    expect(await screen.findByTestId('interview-job-empty')).toBeVisible()
    expect(screen.queryByTestId('setup-position-input')).not.toBeInTheDocument()
    expect(screen.queryByTestId('setup-company-input')).not.toBeInTheDocument()
  })

  it('requests jobs within the backend-supported page limit', async () => {
    renderModeSelect()

    await screen.findByTestId('interview-launch-workbench')
    expect(mocks.useJobsParams).toEqual({ limit: 50 })
  })

  it('requires job and resume context and only shows mode-specific parameters', async () => {
    renderModeSelect('/interview/mode?job_id=job-1')

    expect(await screen.findByTestId('interview-launch-workbench')).toBeVisible()
    expect(screen.getByTestId('interview-job-jd')).toHaveTextContent('Original JD')
    expect(screen.getByTestId('interview-resume-picker')).toHaveValue('resume-1')
    expect(screen.queryByTestId('setup-position-input')).not.toBeInTheDocument()
    expect(screen.queryByTestId('setup-company-input')).not.toBeInTheDocument()

    expect(screen.getByTestId('full-interview-config-option-10')).toBeVisible()
    fireEvent.click(screen.getByTestId('mode-doubao'))
    expect(screen.getByText(/豆包 Prompt 生成/)).toBeVisible()
    expect(screen.queryByTestId('full-interview-config-option-10')).not.toBeInTheDocument()
  })

  it('creates doubao sessions from job/resume and generates a plan before routing', async () => {
    renderModeSelect('/interview/mode?job_id=job-1')

    await screen.findByTestId('interview-launch-workbench')
    fireEvent.click(screen.getByTestId('mode-doubao'))
    fireEvent.click(screen.getByTestId('interview-start-button'))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1))
    expect(mocks.create.mock.calls[0][0]).toEqual({
      job_id: 'job-1',
      branch_id: 'resume-1',
      mode: 'doubao',
      max_questions: undefined,
      use_variants: false,
    })
    expect(mocks.create.mock.calls[0][0]).not.toHaveProperty('position')
    expect(mocks.create.mock.calls[0][0]).not.toHaveProperty('company')
    expect(mocks.generatePlan).toHaveBeenCalledWith('session-1')
    expect(mocks.start).not.toHaveBeenCalled()
    expect(mocks.navigate).toHaveBeenCalledWith('/interview/session-1/live')
  })

  it('keeps quick drill disabled when the error pool is insufficient', async () => {
    renderModeSelect()

    const quickDrill = await screen.findByTestId('quick-drill')
    expect(quickDrill).toBeDisabled()
    expect(useInterviewModeStore.getState().mode).toBe('full')
  })
})

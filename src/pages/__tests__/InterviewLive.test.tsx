/** 019 — InterviewLive 启动页 ?job_id= 预填（US3, FR-012）。 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock WebSocket hook to avoid opening a real socket in jsdom.
vi.mock('@/hooks/useInterviewWS', () => ({
  useInterviewWS: () => ({
    state: {
      connected: false,
      reconnecting: false,
      reconnectAttempt: 0,
      currentNode: null,
      currentQuestion: 0,
      totalQuestions: 5,
      streamingText: '',
      lastCheckpointId: null,
      error: null,
      events: [],
    },
    connect: vi.fn(),
    submitAnswer: vi.fn(),
    reconnect: vi.fn(),
  }),
}))

// Stub branches so the picker has options and the prefill can land on one.
const MOCK_BRANCHES = [
  {
    id: '01900000-0000-7000-8000-000000000m01',
    user_id: 'u-1',
    parent_id: null,
    name: '主简历',
    is_main: true,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-12T00:00:00Z',
    last_edited_at: null,
  },
]
vi.mock('@/hooks/queries/useResumeBranches', () => ({
  useResumeBranches: () => ({ data: MOCK_BRANCHES, isLoading: false }),
}))

import InterviewLive from '@/pages/InterviewLive'

function renderWith(initialUrl: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <Routes>
          <Route path="/interview" element={<InterviewLive />} />
          <Route path="/interview/:id" element={<InterviewLive />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('InterviewLive — ?job_id 预填 (019)', () => {
  it('renders the prefill card and prefills position/company from job', async () => {
    renderWith('/interview?new=1&job_id=job-mock-1')

    // wait for useJob to resolve via MSW
    const card = await screen.findByTestId('intake-prefill-card')
    expect(card.textContent).toContain('字节')
    expect(card.textContent).toContain('高级前端')

    const positionInput = (await screen.findByTestId('setup-position-input')) as HTMLInputElement
    const companyInput = (await screen.findByTestId('setup-company-input')) as HTMLInputElement
    expect(positionInput.value).toBe('高级前端')
    expect(companyInput.value).toBe('字节')
  })

  it('prefills branch_id when ?branch_id is present', async () => {
    renderWith(
      '/interview?new=1&job_id=job-mock-1&branch_id=01900000-0000-7000-8000-000000000m01',
    )

    await screen.findByTestId('intake-prefill-card')

    await waitFor(() => {
      const select = screen
        .getByTestId('setup-resume-picker')
        .querySelector('select') as HTMLSelectElement
      expect(select.value).toBe('01900000-0000-7000-8000-000000000m01')
    })
  })

  it('renders the requirements card with foldable body when requirements_md ≥ 50 chars', async () => {
    renderWith('/interview?new=1&job_id=job-mock-1')

    const reqCard = await screen.findByTestId('intake-requirements-card')
    expect(reqCard.textContent).toContain('岗位招聘需求')

    // expand the card by clicking the toggle button
    const toggleBtn = reqCard.querySelector('button')!
    fireEvent.click(toggleBtn)

    // After expansion, the body shows the requirements_md content
    await waitFor(() => {
      expect(reqCard.textContent).toContain('3年以上 React 经验')
    })
  })

  it('does not render the prefill card when ?job_id is missing', async () => {
    renderWith('/interview?new=1')

    // wait for any setup chrome
    await screen.findByTestId('setup-position-input')
    expect(screen.queryByTestId('intake-prefill-card')).not.toBeInTheDocument()
    expect(screen.queryByTestId('intake-requirements-card')).not.toBeInTheDocument()

    const positionInput = screen.getByTestId('setup-position-input') as HTMLInputElement
    const companyInput = screen.getByTestId('setup-company-input') as HTMLInputElement
    expect(positionInput.value).toBe('')
    expect(companyInput.value).toBe('')
  })
})

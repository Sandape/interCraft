/** 018 #10 — ErrorCoachPanel shows Chinese feedback for loading / error states. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import ErrorCoachPanel from '@/components/error-book/ErrorCoachPanel'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

const { startMock, submitAnswerMock, abortMock, resetMock, mockState } = vi.hoisted(() => ({
  startMock: vi.fn(),
  submitAnswerMock: vi.fn(),
  abortMock: vi.fn(),
  resetMock: vi.fn(),
  mockState: {
    loading: false,
    error: null as string | null,
    threadId: null as string | null,
    status: null as string | null,
    correctCount: 0,
    attemptCount: 0,
    hintLevel: null as string | null,
    hintContent: null as string | null,
    score: null as number | null,
  },
}))

vi.mock('@/hooks/useErrorCoach', () => ({
  useErrorCoach: () => ({
    ...mockState,
    start: startMock,
    submitAnswer: submitAnswerMock,
    abort: abortMock,
    reset: resetMock,
  }),
}))

beforeEach(() => {
  startMock.mockReset()
  submitAnswerMock.mockReset()
  abortMock.mockReset()
  resetMock.mockReset()
  Object.assign(mockState, {
    loading: false,
    error: null,
    threadId: null,
    status: null,
    correctCount: 0,
    attemptCount: 0,
    hintLevel: null,
    hintContent: null,
    score: null,
  })
})

function renderPanel(open = true) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ErrorCoachPanel
          errorQuestionId="eq-1"
          questionText="What is React?"
          open={open}
          onClose={() => {}}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ErrorCoachPanel — user feedback (018 #10)', () => {
  it('renders the start button when idle', () => {
    renderPanel()
    expect(screen.getByTestId('coach-start-button')).toBeInTheDocument()
    expect(screen.getByTestId('coach-start-button')).toHaveTextContent('开始强化')
  })

  it('shows Chinese loading text when loading is true', () => {
    mockState.loading = true
    mockState.threadId = 'th-1'
    mockState.status = 'starting'

    renderPanel()
    expect(screen.getByTestId('coach-loading')).toBeInTheDocument()
    expect(screen.getByText('正在启动强化辅导…')).toBeInTheDocument()
  })

  it('shows error text and retry button when error is set', () => {
    mockState.error = '启动失败，请重试'
    mockState.status = 'error'

    renderPanel()
    expect(screen.getByTestId('coach-error')).toBeInTheDocument()
    expect(screen.getByText('启动失败，请重试')).toBeInTheDocument()
    expect(screen.getByTestId('coach-retry-button')).toBeInTheDocument()
  })
})
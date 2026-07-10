/**
 * REQ-058 US4 — plan failure banner and degrade confirm UX.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import InterviewLive from '@/pages/InterviewLive'

vi.mock('@/hooks/useInterviewWS', () => ({
  useInterviewWS: () => ({
    state: {
      connected: true,
      reconnecting: false,
      reconnectAttempt: 0,
      currentNode: null,
      currentQuestion: 0,
      totalQuestions: 10,
      streamingText: '',
      lastCheckpointId: 'ckpt-1',
      error: null,
      events: [],
      turnPhase: 'idle',
    },
    connect: vi.fn(),
    submitAnswer: vi.fn(),
    reconnect: vi.fn(),
  }),
}))

vi.mock('@/api/token-storage', () => ({
  getAccessToken: () => 'test-token',
}))

vi.mock('@/stores/useAuthStore', () => ({
  useAuthStore: (sel: (s: { user: { email: string; display_name: string } | null }) => unknown) =>
    sel({ user: { email: 'test@example.com', display_name: 'Tester' } }),
}))

vi.mock('@/hooks/queries/useAvatarBlob', () => ({
  useAvatarBlob: () => null,
}))

const mockGetById = vi.fn()
const mockResume = vi.fn()
const mockConfirmPlanDegrade = vi.fn()

vi.mock('@/repositories/interviewSessionRepo', async () => {
  const actual = await vi.importActual<typeof import('@/repositories/interviewSessionRepo')>(
    '@/repositories/interviewSessionRepo',
  )
  return {
    ...actual,
    interviewSessionRepo: {
      getById: (...args: unknown[]) => mockGetById(...args),
      resume: (...args: unknown[]) => mockResume(...args),
      confirmPlanDegrade: (...args: unknown[]) => mockConfirmPlanDegrade(...args),
    },
  }
})

function renderLive() {
  return render(
    <MemoryRouter initialEntries={['/interview/session-plan-fail/live']}>
      <Routes>
        <Route path="/interview/:id/live" element={<InterviewLive />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('InterviewLive — plan failure UX (REQ-058)', () => {
  beforeEach(() => {
    ;(globalThis as any).__VITE_USE_MOCK_OVERRIDE__ = 'false'
    mockConfirmPlanDegrade.mockResolvedValue({
      data: {
        id: 'session-plan-fail',
        plan_status: 'degraded',
        degraded: true,
        plan_error_message: null,
        interview_plan: null,
        web_research: null,
      },
    })
    mockGetById.mockResolvedValue({
      id: 'session-plan-fail',
      status: 'in_progress',
      mode: 'full',
      max_questions: 10,
      position: 'AI PM',
      company: 'Acme',
      plan_status: 'failed',
      plan_error_code: 'QUOTA_EXCEEDED',
      plan_error_message: '今日计划生成额度已用完，请明天再试或降级继续。',
      degraded: false,
      interview_plan: null,
      web_research: null,
    })
    mockResume.mockResolvedValue({
      data: {
        values: {
          questions: [],
          scores: [],
          messages: [],
        },
      },
    })
  })

  it('surfaces failed plan banner with error message and blocks input until degrade confirm', async () => {
    renderLive()

    const banner = await screen.findByTestId('plan-phase-banner-failed')
    expect(banner).toHaveTextContent('今日计划生成额度已用完')

    const input = screen.getByTestId('answer-input') as HTMLTextAreaElement
    expect(input.disabled).toBe(true)

    fireEvent.click(screen.getByTestId('plan-degrade-confirm'))

    await waitFor(() => {
      expect(mockConfirmPlanDegrade).toHaveBeenCalledWith('session-plan-fail')
    })

    await waitFor(() => {
      expect(screen.getByTestId('plan-phase-banner-degraded')).toBeVisible()
    })
  })
})

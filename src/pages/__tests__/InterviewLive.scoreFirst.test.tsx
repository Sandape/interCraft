/**
 * REQ-058 US3 — score-first UX: score visible before next question arrives.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import InterviewLive from '@/pages/InterviewLive'

const scoreEvent = {
  type: 'node.completed',
  event_id: 'evt-score-1',
  session_id: 'session-score-first',
  timestamp: '2026-07-10T00:00:00Z',
  node_name: 'score',
  payload: {
    summary: {
      question_no: 1,
      score: 8,
      dimension: '技术深度',
      feedback: '回答结构清晰。',
      sub_scores: {},
    },
  },
}

const wsState = {
  connected: true,
  reconnecting: false,
  reconnectAttempt: 0,
  currentNode: null,
  currentQuestion: 1,
  totalQuestions: 10,
  streamingText: '',
  lastCheckpointId: 'ckpt-1',
  error: null,
  events: [scoreEvent],
  turnPhase: 'awaiting_question' as const,
  taskId: null,
  executionId: null,
  availableActions: [],
  pointsSummary: null,
  seenSequences: [],
}

vi.mock('@/hooks/useInterviewWS', () => ({
  useInterviewWS: () => ({
    state: wsState,
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

vi.mock('@/repositories/interviewSessionRepo', async () => {
  const actual = await vi.importActual<typeof import('@/repositories/interviewSessionRepo')>(
    '@/repositories/interviewSessionRepo',
  )
  return {
    ...actual,
    interviewSessionRepo: {
      getById: (...args: unknown[]) => mockGetById(...args),
      resume: (...args: unknown[]) => mockResume(...args),
    },
  }
})

function renderLive() {
  return render(
    <MemoryRouter initialEntries={['/interview/session-score-first/live']}>
      <Routes>
        <Route path="/interview/:id/live" element={<InterviewLive />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('InterviewLive — score-first UX (REQ-058)', () => {
  beforeEach(() => {
    ;(globalThis as any).__VITE_USE_MOCK_OVERRIDE__ = 'false'
    mockGetById.mockResolvedValue({
      id: 'session-score-first',
      status: 'in_progress',
      mode: 'full',
      max_questions: 10,
      position: 'AI PM',
      company: 'Acme',
      plan_status: 'ready',
      degraded: false,
      interview_plan: { suggested_questions: ['Q1'] },
      web_research: null,
    })
    mockResume.mockResolvedValue({
      data: {
        values: {
          questions: [{ question: '第一题', dimension: '技术深度', expected_points: [], hints: [] }],
          scores: [{
            question_no: 1,
            score: 8,
            dimension: '技术深度',
            feedback: '回答结构清晰。',
            sub_scores: {},
          }],
          messages: [
            { role: 'user', content: '自我介绍' },
            { role: 'user', content: '我的回答' },
          ],
        },
      },
    })
  })

  it('shows score feedback and next-question wait copy while input stays disabled', async () => {
    renderLive()

    await waitFor(() => {
      expect(screen.getByTestId('score-first-pending')).toBeVisible()
    })

    expect(screen.getByText('8/10')).toBeVisible()
    expect(screen.getByText('正在出下一题')).toBeVisible()

    const input = screen.getByTestId('answer-input') as HTMLTextAreaElement
    expect(input.disabled).toBe(true)
    expect(input.placeholder).toContain('正在出下一题')
  })
})

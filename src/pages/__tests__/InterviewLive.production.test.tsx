/**
 * REQ-061 T071 — InterviewLive production UX (US4).
 *
 * Covers score-before-next-question, canonical pause/resume actions,
 * reconnect event-sequence dedupe, saved-round explanation, and report failure.
 * May fail until T076 wires FE to server actions / runtime envelope.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import InterviewLive from '@/pages/InterviewLive'

const scoreEvent = {
  type: 'round.score',
  event_id: 'evt-score-1',
  session_id: 'session-prod-061',
  timestamp: '2026-07-11T00:00:00Z',
  node_name: 'score',
  sequence: 1,
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

const nextQuestionEvent = {
  type: 'round.next_question',
  event_id: 'evt-q-2',
  session_id: 'session-prod-061',
  timestamp: '2026-07-11T00:00:05Z',
  node_name: 'interviewer',
  sequence: 2,
  payload: {
    question: '请说明一次跨团队协作经历。',
    question_no: 2,
  },
}

const duplicateScoreEvent = { ...scoreEvent, event_id: 'evt-score-1-dup' }

let wsState: Record<string, unknown>
let submitAnswer: ReturnType<typeof vi.fn>
let reconnect: ReturnType<typeof vi.fn>
let pauseInterview: ReturnType<typeof vi.fn>
let resumeInterview: ReturnType<typeof vi.fn>

vi.mock('@/hooks/useInterviewWS', () => ({
  useInterviewWS: () => ({
    state: wsState,
    connect: vi.fn(),
    submitAnswer,
    reconnect,
    pause: pauseInterview,
    resume: resumeInterview,
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
const mockPause = vi.fn()
const mockActiveEnd = vi.fn()

vi.mock('@/repositories/interviewSessionRepo', async () => {
  const actual = await vi.importActual<typeof import('@/repositories/interviewSessionRepo')>(
    '@/repositories/interviewSessionRepo',
  )
  return {
    ...actual,
    interviewSessionRepo: {
      getById: (...args: unknown[]) => mockGetById(...args),
      resume: (...args: unknown[]) => mockResume(...args),
      pause: (...args: unknown[]) => mockPause(...args),
      activeEnd: (...args: unknown[]) => mockActiveEnd(...args),
    },
  }
})

function renderLive(id = 'session-prod-061') {
  return render(
    <MemoryRouter initialEntries={[`/interview/${id}/live`]}>
      <Routes>
        <Route path="/interview/:id/live" element={<InterviewLive />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('InterviewLive — production lifecycle (REQ-061 US4)', () => {
  beforeEach(() => {
    ;(globalThis as any).__VITE_USE_MOCK_OVERRIDE__ = 'false'
    submitAnswer = vi.fn()
    reconnect = vi.fn()
    pauseInterview = vi.fn()
    resumeInterview = vi.fn()
    wsState = {
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
      turnPhase: 'awaiting_question',
      availableActions: ['pause', 'resume', 'cancel', 'end'],
      taskId: 'task-061-1',
      executionId: 'exec-061-1',
      pointsSummary: { reserved: 200, settled: 40, currency: 'points' },
      seenSequences: [1],
    }
    mockGetById.mockResolvedValue({
      id: 'session-prod-061',
      status: 'in_progress',
      mode: 'full',
      max_questions: 10,
      position: 'AI PM',
      company: 'Acme',
      plan_status: 'ready',
      degraded: false,
      interview_plan: { suggested_questions: ['Q1'] },
      web_research: null,
      task_id: 'task-061-1',
      execution_id: 'exec-061-1',
      available_actions: ['pause', 'cancel', 'end'],
      points_summary: { reserved: 200, settled: 40 },
    })
    mockResume.mockResolvedValue({
      data: {
        values: {
          questions: [{ question: '第一题', dimension: '技术深度', expected_points: [], hints: [] }],
          scores: [
            {
              question_no: 1,
              score: 8,
              dimension: '技术深度',
              feedback: '回答结构清晰。',
              sub_scores: {},
            },
          ],
          messages: [
            { role: 'user', content: '自我介绍' },
            { role: 'user', content: '我的回答' },
          ],
        },
        available_actions: ['pause', 'cancel', 'end'],
        task_id: 'task-061-1',
        execution_id: 'exec-061-1',
      },
    })
    mockPause.mockResolvedValue({
      status: 'paused',
      pause_deadline: '2026-07-18T00:00:00Z',
      available_actions: ['resume'],
    })
  })

  it('shows score before next question arrives (score-first)', async () => {
    renderLive()
    await waitFor(() => {
      expect(screen.getByTestId('score-first-pending')).toBeInTheDocument()
    })
    const pending = screen.getByTestId('score-first-score')
    expect(pending.textContent).toMatch(/回答结构清晰/)
    expect(pending.textContent).toMatch(/8\/10/)
    // Pending owns the score until next question; avoid duplicate thread card
    expect(screen.queryByTestId('answer-score-card')).toBeNull()
    // Next question not yet in events — must not claim question 2 visible as primary
    expect(screen.queryByText('请说明一次跨团队协作经历。')).toBeNull()
  })

  it('renders canonical pause/resume actions from server available_actions', async () => {
    renderLive()
    await waitFor(() => {
      expect(screen.getByTestId('interview-action-pause')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('interview-action-pause'))
    await waitFor(() => {
      expect(mockPause).toHaveBeenCalled()
    })

    // After pause, server offers resume
    mockGetById.mockResolvedValueOnce({
      id: 'session-prod-061',
      status: 'paused',
      mode: 'full',
      max_questions: 10,
      position: 'AI PM',
      company: 'Acme',
      plan_status: 'ready',
      degraded: false,
      available_actions: ['resume'],
      pause_deadline: '2026-07-18T00:00:00Z',
    })
    wsState = {
      ...wsState,
      availableActions: ['resume'],
    }
    renderLive('session-prod-061-paused')
    await waitFor(() => {
      expect(screen.getByTestId('interview-action-resume')).toBeInTheDocument()
    })
  })

  it('dedupes reconnect events by sequence number', async () => {
    wsState = {
      ...wsState,
      events: [scoreEvent, duplicateScoreEvent, nextQuestionEvent],
      seenSequences: [1, 2],
      turnPhase: 'idle',
      currentQuestion: 2,
    }
    renderLive()
    await waitFor(() => {
      // Thread score card once despite duplicate reconnect event (+ sidebar may mirror)
      expect(screen.getAllByTestId('answer-score-card')).toHaveLength(1)
      expect(screen.getByText('请说明一次跨团队协作经历。')).toBeInTheDocument()
    })
  })

  it('explains saved round after reconnect', async () => {
    mockResume.mockResolvedValueOnce({
      data: {
        values: {
          questions: [{ question: '已保存的题目', dimension: '沟通', expected_points: [], hints: [] }],
          scores: [
            {
              question_no: 1,
              score: 7,
              dimension: '沟通',
              feedback: '已保存本轮评分。',
              sub_scores: {},
            },
          ],
          messages: [{ role: 'user', content: '已保存的回答' }],
        },
        available_actions: ['pause', 'cancel', 'end'],
        saved_round_explanation: '已恢复第 1 轮评分与回答，可继续作答。',
      },
    })
    renderLive()
    await waitFor(() => {
      expect(screen.getByTestId('saved-round-explanation')).toBeInTheDocument()
    })
    expect(screen.getByTestId('saved-round-explanation').textContent).toMatch(/已恢复/)
  })

  it('surfaces report failure without claiming full success', async () => {
    mockGetById.mockResolvedValueOnce({
      id: 'session-prod-061',
      status: 'partially_succeeded',
      mode: 'full',
      max_questions: 10,
      position: 'AI PM',
      company: 'Acme',
      plan_status: 'ready',
      degraded: false,
      available_actions: ['retry_failed_component', 'open_result'],
      failure: {
        code: 'REPORT_ASSEMBLY_FAILED',
        message: '报告生成失败，已完成评分已保留。',
        safe: true,
      },
      points_summary: { reserved: 200, settled: 80 },
    })
    wsState = {
      ...wsState,
      turnPhase: 'idle',
      events: [scoreEvent],
      error: {
        type: 'error',
        event_id: 'err-report',
        session_id: 'session-prod-061',
        timestamp: '2026-07-11T01:00:00Z',
        node_name: 'report',
        payload: { code: 'REPORT_ASSEMBLY_FAILED', message: '报告生成失败，已完成评分已保留。' },
      },
    }
    renderLive()
    await waitFor(() => {
      expect(screen.getByTestId('interview-report-failure')).toBeInTheDocument()
    })
    expect(screen.getByTestId('interview-report-failure').textContent).toMatch(/评分已保留/)
    expect(screen.queryByTestId('interview-completed-state')).toBeNull()
  })
})

describe('InterviewLive — resume data validation (REQ-061 regression)', () => {
  beforeEach(() => {
    ;(globalThis as typeof globalThis & { __VITE_USE_MOCK_OVERRIDE__?: string })
      .__VITE_USE_MOCK_OVERRIDE__ = 'false'
    wsState = {
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
      turnPhase: 'awaiting_question',
      availableActions: [],
      taskId: null,
      executionId: null,
      pointsSummary: null,
      seenSequences: [],
    }
    mockGetById.mockResolvedValue({
      id: 'session-val',
      status: 'in_progress',
      mode: 'full',
      max_questions: 10,
      position: 'AI PM',
      company: 'Acme',
      plan_status: 'ready',
      degraded: false,
      interview_plan: null,
      web_research: null,
    })
    mockResume.mockResolvedValue({
      data: {
        values: { questions: [], scores: [], messages: [] },
      },
    })
  })

  it('fails safely to empty restored questions when API returns null', async () => {
    mockResume.mockResolvedValueOnce({
      data: { values: { questions: null, scores: [], messages: [{ role: 'user', content: '回答' }] } },
    })
    renderLive('session-val-null')
    await waitFor(() => {
      expect(screen.getByTestId('answer-input')).toBeInTheDocument()
    })
  })

  it('fails safely to empty restored questions when API returns a string', async () => {
    mockResume.mockResolvedValueOnce({
      data: { values: { questions: 'not-an-array', scores: [], messages: [{ role: 'user', content: '回答' }] } },
    })
    renderLive('session-val-str')
    await waitFor(() => {
      expect(screen.getByTestId('answer-input')).toBeInTheDocument()
    })
  })

  it('fails safely to empty restored scores when API returns an object', async () => {
    mockResume.mockResolvedValueOnce({
      data: {
        values: {
          questions: [{ question: '正常题', dimension: '技术深度', expected_points: [], hints: [] }],
          scores: { invalid: 'object' },
          messages: [{ role: 'user', content: '回答' }],
        },
      },
    })
    renderLive('session-val-obj')
    await waitFor(() => {
      expect(screen.getByTestId('answer-input')).toBeInTheDocument()
    })
  })

  it('uses sequence_no as question_no when question_no is 0', async () => {
    mockResume.mockResolvedValueOnce({
      data: {
        values: {
          questions: [
            { question: 'Sequence Q', dimension: '技术深度', expected_points: [], hints: [], question_no: 0, sequence_no: 3 },
          ],
          scores: [
            {
              question_no: 0,
              sequence_no: 3,
              score: 6,
              dimension: '序号回退维度',
              feedback: '序号回退评分',
              sub_scores: {},
            },
          ],
          messages: [{ role: 'user', content: '回答' }],
        },
      },
    })
    renderLive('session-val-seq')
    await waitFor(() => {
      expect(screen.getByText('Sequence Q')).toBeInTheDocument()
    })
    const restoredScore = screen
      .getAllByText('序号回退维度')
      .map((element) => element.parentElement)
      .find((element) => element?.textContent?.includes('3') && element.textContent.includes('6'))
    expect(restoredScore).toBeDefined()
    expect(restoredScore).toHaveTextContent('3')
    expect(restoredScore).toHaveTextContent('6')
  })

  it('treats question_no 3 and question_no 0 / sequence_no 3 as the same restored question', async () => {
    mockResume.mockResolvedValueOnce({
      data: {
        values: {
          questions: [
            {
              question_no: 3,
              question: '第三题主记录',
              dimension: '技术深度',
              expected_points: [],
              hints: [],
            },
            {
              question_no: 0,
              sequence_no: 3,
              question: '第三题重复记录',
              dimension: '技术深度',
              expected_points: [],
              hints: [],
            },
          ],
          scores: [],
          messages: [
            { role: 'user', content: '回答1' },
            { role: 'user', content: '回答2' },
          ],
        },
      },
    })

    renderLive('session-val-effective-question')

    await waitFor(() => {
      expect(screen.getByText('第三题主记录')).toBeInTheDocument()
    })
    expect(screen.queryByText('第三题重复记录')).not.toBeInTheDocument()
  })

  it('treats question_no 3 and question_no 0 / sequence_no 3 as the same restored score', async () => {
    mockResume.mockResolvedValueOnce({
      data: {
        values: {
          questions: [],
          scores: [
            {
              question_no: 3,
              score: 7,
              dimension: '统一序号评分维度',
              feedback: '主评分',
              sub_scores: {},
            },
            {
              question_no: 0,
              sequence_no: 3,
              score: 9,
              dimension: '统一序号评分维度',
              feedback: '重复评分',
              sub_scores: {},
            },
          ],
          messages: [],
        },
      },
    })

    renderLive('session-val-effective-score')

    await waitFor(() => {
      // One dimension-average label plus one retained score-history row.
      expect(screen.getAllByText('统一序号评分维度')).toHaveLength(2)
    })
  })

  it('keeps scores without an effective question number even when feedback and score match', async () => {
    mockResume.mockResolvedValueOnce({
      data: {
        values: {
          questions: [],
          scores: [
            {
              score: 5,
              dimension: '无编号维度A',
              feedback: '相同反馈',
              sub_scores: {},
            },
            {
              question_no: 0,
              sequence_no: 0,
              score: 5,
              dimension: '无编号维度B',
              feedback: '相同反馈',
              sub_scores: {},
            },
          ],
          messages: [],
        },
      },
    })

    renderLive('session-val-unidentified-scores')

    await waitFor(() => {
      expect(screen.getAllByText('无编号维度A')).toHaveLength(2)
      expect(screen.getAllByText('无编号维度B')).toHaveLength(2)
    })
  })

  it('dedupes restored questions by text when both IDs are absent', async () => {
    mockResume.mockResolvedValueOnce({
      data: {
        values: {
          questions: [
            { question: '重复题', dimension: '技术深度', expected_points: [], hints: [] },
            { question: '重复题', dimension: '技术深度', expected_points: [], hints: [] },
            { question: '独立题', dimension: '沟通', expected_points: [], hints: [] },
          ],
          scores: [],
          messages: [
            { role: 'user', content: '回答1' },
            { role: 'user', content: '回答2' },
          ],
        },
      },
    })
    renderLive('session-val-dedup')
    await waitFor(() => {
      const elements = screen.getAllByText('重复题')
      expect(elements).toHaveLength(1)
      expect(screen.getByText('独立题')).toBeInTheDocument()
    })
  })
})

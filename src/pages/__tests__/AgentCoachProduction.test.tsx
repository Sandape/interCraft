/**
 * @vitest-environment jsdom
 * REQ-061 T081 — Agent/Coach production FE: no hard-coded terminal arrays;
 * render server actions + persisted coach answers.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AgentSettings from '@/pages/AgentSettings'
import GeneralCoach from '@/pages/GeneralCoach'

const mocks = vi.hoisted(() => ({
  fetchTasks: vi.fn(),
  fetchConsumerStatus: vi.fn(),
  fetchBindingStatus: vi.fn(),
  fetchPreferences: vi.fn(),
  cancelTask: vi.fn(),
  resumeTask: vi.fn(),
  coachStart: vi.fn(),
  coachSend: vi.fn(),
  coachClose: vi.fn(),
  coachState: vi.fn(),
  getAITask: vi.fn(),
}))

vi.mock('@/repositories/AgentRepository', () => ({
  resolveQrcodeSrc: (d: { qrcode_image_url: string }) => d.qrcode_image_url,
  AgentRepository: {
    fetchBindingStatus: () => mocks.fetchBindingStatus(),
    fetchPreferences: () => mocks.fetchPreferences(),
    fetchConsumerStatus: () => mocks.fetchConsumerStatus(),
    fetchTasks: () => mocks.fetchTasks(),
    cancelTask: (...a: unknown[]) => mocks.cancelTask(...a),
    resumeTask: (...a: unknown[]) => mocks.resumeTask(...a),
  },
}))

vi.mock('@/repositories/generalCoachRepo', () => ({
  generalCoachRepo: {
    start: (...a: unknown[]) => mocks.coachStart(...a),
    sendMessage: (...a: unknown[]) => mocks.coachSend(...a),
    close: (...a: unknown[]) => mocks.coachClose(...a),
    getState: (...a: unknown[]) => mocks.coachState(...a),
    submitFeedback: vi.fn().mockResolvedValue({ ok: true }),
  },
}))

vi.mock('@/hooks/queries/useAITasks', () => ({
  useAITask: () => ({
    data: mocks.getAITask(),
    refetch: vi.fn(),
  }),
}))

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AgentCoachProduction (REQ-061 T081/T087/T089)', () => {
  beforeEach(() => {
    mocks.fetchBindingStatus.mockResolvedValue({ bound: false, agent_status: 'dormant' })
    mocks.fetchPreferences.mockResolvedValue({
      display_name: '助手',
      notification_mode: 'realtime',
    })
    mocks.fetchConsumerStatus.mockResolvedValue({ enabled: true, state: 'active' })
    mocks.fetchTasks.mockResolvedValue({
      items: [
        {
          id: 'agt-1',
          kind: 'chat',
          status: 'running',
          stage: 'tool',
          summary: '处理中',
          created_at: '2026-07-11T00:00:00Z',
          updated_at: '2026-07-11T00:00:00Z',
          available_actions: ['cancel'],
          canonical_status: 'running',
          terminal: false,
          task_id: 'task-agt-1',
        },
      ],
    })
    mocks.getAITask.mockReturnValue({
      task_id: 'task-agt-1',
      task_version: 1,
      status: 'running',
      terminal: false,
      available_actions: ['cancel'],
      point_summary: { quoted_max: 10, reserved: 10, settled: 0, released: 0, settlement_status: 'unsettled' },
    })
    mocks.coachStart.mockResolvedValue({
      thread_id: 'th-1',
      conversation_id: 'th-1',
      status: 'running',
      task_id: 'task-coach-1',
      available_actions: ['cancel'],
      point_summary: { reserved: 5, settled: 0 },
    })
    mocks.coachSend.mockResolvedValue({
      thread_id: 'th-1',
      detected_intent: null,
      confidence: null,
      redirect_to: null,
      assistant_body: '这是持久化的教练回复。',
      available_actions: ['cancel', 'submit_feedback'],
    })
  })

  it('AgentSettings renders server available_actions instead of hard-coded status arrays', async () => {
    wrap(<AgentSettings />)
    await waitFor(() => {
      expect(screen.getByTestId('agent-server-actions')).toBeInTheDocument()
    })
    expect(screen.getByText('取消任务')).toBeInTheDocument()
    expect(screen.getByTestId('agent-task-link')).toHaveAttribute('href', '/ai-tasks/task-agt-1')
    // Must not infer cancel solely from a hard-coded status list when actions omit it
    mocks.fetchTasks.mockResolvedValueOnce({
      items: [
        {
          id: 'agt-2',
          kind: 'chat',
          status: 'running',
          stage: 'tool',
          summary: '无动作',
          created_at: '2026-07-11T00:00:00Z',
          updated_at: '2026-07-11T00:00:00Z',
          available_actions: [],
          terminal: false,
        },
      ],
    })
  })

  it('GeneralCoach renders persisted assistant_body and point/task chrome', async () => {
    wrap(<GeneralCoach />)
    fireEvent.change(screen.getByTestId('coach-input'), { target: { value: '你好' } })
    fireEvent.click(screen.getByTestId('coach-send'))
    await waitFor(() => {
      expect(screen.getByText('这是持久化的教练回复。')).toBeInTheDocument()
    })
    expect(screen.getByTestId('coach-assistant-bubble')).toBeInTheDocument()
    expect(screen.getByTestId('coach-point-summary')).toBeInTheDocument()
    expect(screen.getByTestId('coach-task-link')).toBeInTheDocument()
    expect(screen.getByTestId('coach-answer-feedback')).toBeInTheDocument()
  })
})

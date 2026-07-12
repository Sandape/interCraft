/**
 * REQ-061 T028 — AI task presentation (US1) failing-first Vitest.
 *
 * Imports shared components / hooks that land in T032–T033. Missing modules
 * are the expected red reason until those tasks ship. Do not stub production
 * components here — only assert server-derived terminal/actions, status/stage,
 * progress, failure explanation, polling/SSE dedupe, and query keys.
 */
import { describe, expect, it } from 'vitest'
import { createElement, type ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { components } from '@/types/generated/ai-runtime'

import { AITaskStatus } from '@/components/ai/AITaskStatus'
import { AIMilestoneList } from '@/components/ai/AIMilestoneList'
import { AIFailurePanel } from '@/components/ai/AIFailurePanel'
import {
  aiTaskKeys,
  dedupeTaskEventsBySequence,
  useAITaskDetail,
  useAITaskEvents,
} from '@/hooks/queries/useAITasks'

type TaskStatus = components['schemas']['TaskStatus']
type TaskDetail = components['schemas']['TaskDetail']
type TaskEvent = components['schemas']['TaskEvent']
type FailurePresentation = components['schemas']['FailurePresentation']

const TERMINAL: ReadonlySet<TaskStatus> = new Set([
  'succeeded',
  'partially_succeeded',
  'failed',
  'cancelled',
  'expired',
])

function wrap(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(createElement(QueryClientProvider, { client }, ui))
}

function baseDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return {
    task_id: '01900000-0000-7000-8000-0000000000aa',
    capability: 'resume_derive',
    action: 'derive',
    status: 'running',
    stage: { code: 'draft', label: '生成草稿', progress_percent: 40 },
    service_tier: 'standard',
    accepted_at: '2026-07-11T12:00:00Z',
    terminal_at: null,
    terminal: false,
    available_actions: ['cancel', 'submit_feedback'],
    point_summary: {
      quoted_max: 100,
      reserved: 100,
      settled: 0,
      released: 0,
      settlement_status: 'unsettled',
    },
    task_version: 2,
    input_summary: { pages: 2 },
    executions: [
      {
        execution_id: '01900000-0000-7000-8000-0000000000bb',
        execution_no: 1,
        trigger_kind: 'initial',
        source_execution_id: null,
        status: 'running',
        started_at: '2026-07-11T12:00:01Z',
        finished_at: null,
      },
    ],
    milestones: [
      {
        code: 'draft',
        label: '草稿',
        status: 'delivered',
        result_ref: 'res:draft',
        settle_eligible: true,
        points_settled: 30,
        delivered_at: '2026-07-11T12:00:10Z',
      },
      {
        code: 'job_analysis',
        label: '岗位分析',
        status: 'running',
        result_ref: null,
        settle_eligible: false,
        points_settled: 0,
        delivered_at: null,
      },
      {
        code: 'suggestions',
        label: '建议',
        status: 'pending',
        result_ref: null,
        settle_eligible: false,
        points_settled: 0,
        delivered_at: null,
      },
    ],
    result_ref: null,
    failure: null,
    degraded: false,
    degradation_summary: null,
    automatic_retry_count: 0,
    ...overrides,
  }
}

describe('AITaskPresentation — REQ-061 T028', () => {
  it('renders server-derived terminal flag and available_actions without client inference', () => {
    const detail = baseDetail({
      status: 'failed',
      terminal: true,
      available_actions: ['system_failure_retry', 'reexecute', 'submit_feedback'],
      failure: {
        category: 'provider_timeout',
        what_happened: '模型超时',
        what_was_saved: '已生成草稿',
        point_effect: '已释放未交付里程碑点数',
        system_next_step: '可系统重试',
        user_next_steps: ['重试', '查看草稿'],
        support_ref: 'sup-1',
      },
    })

    wrap(createElement(AITaskStatus, { task: detail }))

    expect(screen.getByTestId('ai-task-status')).toHaveAttribute(
      'data-terminal',
      'true',
    )
    expect(screen.getByTestId('ai-task-status')).toHaveAttribute(
      'data-status',
      'failed',
    )
    // Actions come from the server DTO — not a hard-coded per-status map.
    for (const action of detail.available_actions) {
      expect(screen.getByTestId(`ai-task-action-${action}`)).toBeInTheDocument()
    }
    // Client must not invent cancel on a terminal failed task when server omitted it.
    expect(screen.queryByTestId('ai-task-action-cancel')).not.toBeInTheDocument()
    expect(TERMINAL.has(detail.status)).toBe(true)
  })

  it('renders status, stage label, and progress percent from task detail', () => {
    const detail = baseDetail()
    wrap(createElement(AITaskStatus, { task: detail }))

    expect(screen.getByTestId('ai-task-status')).toHaveTextContent(/running|运行/i)
    expect(screen.getByTestId('ai-task-stage')).toHaveTextContent('生成草稿')
    expect(screen.getByTestId('ai-task-progress')).toHaveAttribute(
      'aria-valuenow',
      '40',
    )
  })

  it('renders milestone list progress from server milestones', () => {
    const detail = baseDetail()
    wrap(createElement(AIMilestoneList, { milestones: detail.milestones }))

    expect(screen.getByTestId('ai-milestone-draft')).toHaveAttribute(
      'data-status',
      'delivered',
    )
    expect(screen.getByTestId('ai-milestone-job_analysis')).toHaveAttribute(
      'data-status',
      'running',
    )
    expect(screen.getByTestId('ai-milestone-suggestions')).toHaveAttribute(
      'data-status',
      'pending',
    )
  })

  it('renders failure explanation fields from FailurePresentation', () => {
    const failure: FailurePresentation = {
      category: 'deterministic_policy',
      what_happened: '输入不完整',
      what_was_saved: '无交付结果',
      point_effect: '全额释放预留点数',
      system_next_step: '等待用户补充输入',
      user_next_steps: ['补充材料后重试'],
      support_ref: 'sup-fail-1',
    }
    wrap(createElement(AIFailurePanel, { failure }))

    expect(screen.getByTestId('ai-failure-panel')).toHaveTextContent('输入不完整')
    expect(screen.getByTestId('ai-failure-panel')).toHaveTextContent('全额释放预留点数')
    expect(screen.getByTestId('ai-failure-panel')).toHaveTextContent('补充材料后重试')
    expect(screen.getByTestId('ai-failure-panel')).not.toHaveTextContent(/ECONNRESET|stack/i)
  })

  it('dedupes polling/SSE events by contiguous sequence', () => {
    const events: TaskEvent[] = [
      {
        event_id: 'e1',
        sequence: 1,
        event_type: 'ai.task.accepted',
        occurred_at: '2026-07-11T12:00:00Z',
        recorded_at: '2026-07-11T12:00:00Z',
        status: 'accepted',
        stage: { code: 'accepted', label: '已受理' },
        message: 'accepted',
      },
      {
        event_id: 'e2',
        sequence: 2,
        event_type: 'ai.task.state_changed',
        occurred_at: '2026-07-11T12:00:01Z',
        recorded_at: '2026-07-11T12:00:01Z',
        status: 'queued',
        stage: { code: 'queued', label: '排队' },
        message: 'queued',
      },
      // Duplicate sequence from reconnect overlap
      {
        event_id: 'e2-dup',
        sequence: 2,
        event_type: 'ai.task.state_changed',
        occurred_at: '2026-07-11T12:00:01Z',
        recorded_at: '2026-07-11T12:00:02Z',
        status: 'queued',
        stage: { code: 'queued', label: '排队' },
        message: 'queued',
      },
      {
        event_id: 'e3',
        sequence: 3,
        event_type: 'ai.task.state_changed',
        occurred_at: '2026-07-11T12:00:03Z',
        recorded_at: '2026-07-11T12:00:03Z',
        status: 'running',
        stage: { code: 'draft', label: '生成草稿', progress_percent: 10 },
        message: 'running',
      },
    ]

    const deduped = dedupeTaskEventsBySequence(events)
    expect(deduped.map((e) => e.sequence)).toEqual([1, 2, 3])
    expect(deduped).toHaveLength(3)
    expect(deduped[1]?.event_id).toBe('e2')
  })

  it('namespaces TanStack query keys under aiTasks', () => {
    const taskId = '01900000-0000-7000-8000-0000000000aa'
    expect(aiTaskKeys.all[0]).toBe('aiTasks')
    expect(aiTaskKeys.lists()).toEqual(expect.arrayContaining(['aiTasks', 'list']))
    expect(aiTaskKeys.detail(taskId)[0]).toBe('aiTasks')
    expect(aiTaskKeys.detail(taskId)).toEqual(
      expect.arrayContaining(['aiTasks', 'detail', taskId]),
    )
    expect(aiTaskKeys.events(taskId, 0)).toEqual(
      expect.arrayContaining(['aiTasks', 'events', taskId]),
    )
    // Must not collide with business todo keys.
    expect(aiTaskKeys.all).not.toEqual(['tasks'])
  })

  it('exposes detail and events hooks for reconnect polling', () => {
    expect(typeof useAITaskDetail).toBe('function')
    expect(typeof useAITaskEvents).toBe('function')
  })
})

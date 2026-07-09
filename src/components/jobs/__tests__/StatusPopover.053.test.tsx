/**
 * REQ-053 — StatusPopover unit coverage (T025 + T026 + T027).
 *
 * Asserts:
 *  - The popover shows the NEW 7-state labels (笔试中 / 一面中 / 二面中 /
 *    三面中 / 已失败 / 已通过) — not the legacy OA / HR / Offer / 已拒绝 /
 *    已撤回.
 *  - Picking an interview-round target (interview_1) opens the inline
 *    DateTimePicker; submitting empty value surfaces the inline error
 *    (T026 + client-side future-time validation).
 *  - Terminal jobs (failed / passed) collapse the trigger into a disabled
 *    `data-testid="status-popover-disabled"` element with the tooltip
 *    "已终结的岗位无法推进" (T027).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createElement, type ReactNode } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StatusPopover } from '@/components/jobs/StatusPopover'

const mockNewGraph = {
  statuses: ['applied', 'test', 'interview_1', 'interview_2', 'interview_3', 'failed', 'passed'],
  transitions: [
    { from: 'applied', to: 'test' },
    { from: 'applied', to: 'interview_1' },
    { from: 'applied', to: 'interview_2' },
    { from: 'applied', to: 'interview_3' },
    { from: 'applied', to: 'failed' },
    { from: 'applied', to: 'passed' },
    { from: 'test', to: 'interview_1' },
    { from: 'interview_1', to: 'interview_2' },
    { from: 'interview_1', to: 'failed' },
    { from: 'interview_2', to: 'interview_3' },
    { from: 'interview_2', to: 'passed' },
    { from: 'interview_3', to: 'passed' },
  ],
}

vi.mock('@/hooks/queries/useJobTransitions', () => ({
  useJobTransitions: () => ({ data: mockNewGraph, isStale: false, isLoading: false }),
}))

function wrap(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={qc}>{ui}</QueryClientProvider>,
  )
}

const baseProps = {
  jobId: 'job-x',
  company: 'acme',
  position: 'frontend',
  isPending: false,
  onUpdate: vi.fn(),
  onDelete: vi.fn(),
}

describe('StatusPopover — REQ-053 (T025+T026+T027)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('T025 — popover shows the new 7-state Chinese labels', () => {
    wrap(<StatusPopover {...baseProps} currentStatus="applied" />)
    fireEvent.click(screen.getByTestId('status-popover-trigger'))
    const menu = screen.getByTestId('status-popover-menu')
    for (const label of ['笔试中', '一面中', '二面中', '三面中', '已失败', '已通过']) {
      expect(menu).toHaveTextContent(label)
    }
    // Legacy labels MUST NOT appear.
    expect(menu).not.toHaveTextContent('OA')
    expect(menu).not.toHaveTextContent('HR 面')
    expect(menu).not.toHaveTextContent('Offer')
    expect(menu).not.toHaveTextContent('已拒绝')
    expect(menu).not.toHaveTextContent('已撤回')
  })

  it('T026 — picking interview_1 opens the DateTimePicker marked with *', () => {
    wrap(<StatusPopover {...baseProps} currentStatus="applied" />)
    fireEvent.click(screen.getByTestId('status-popover-trigger'))
    fireEvent.click(screen.getByTestId('status-menuitem-interview_1'))

    const picker = screen.getByTestId('interview-time-picker')
    expect(picker).toBeInTheDocument()
    expect(picker).toHaveTextContent('*')
    // The submit button is the canonical control for advancing.
    expect(screen.getByTestId('interview-time-submit')).toBeInTheDocument()
  })

  it('T026 — submitting an empty time surfaces the inline "面试时间不能为空" error', () => {
    wrap(<StatusPopover {...baseProps} currentStatus="applied" />)
    fireEvent.click(screen.getByTestId('status-popover-trigger'))
    fireEvent.click(screen.getByTestId('status-menuitem-interview_2'))
    fireEvent.click(screen.getByTestId('interview-time-submit'))
    expect(screen.getByTestId('interview-time-error')).toHaveTextContent('面试时间不能为空')
  })

  it('T026 — submitting a past time surfaces the "必须是将来时间" error', () => {
    wrap(<StatusPopover {...baseProps} currentStatus="applied" />)
    fireEvent.click(screen.getByTestId('status-popover-trigger'))
    fireEvent.click(screen.getByTestId('status-menuitem-interview_1'))
    const input = screen.getByTestId('interview-time-input') as HTMLInputElement
    // 24h in the past — well outside the 5-min tolerance.
    const past = new Date(Date.now() - 24 * 60 * 60 * 1000)
    const pad = (n: number) => String(n).padStart(2, '0')
    fireEvent.change(input, {
      target: {
        value: `${past.getFullYear()}-${pad(past.getMonth() + 1)}-${pad(past.getDate())}T${pad(past.getHours())}:${pad(past.getMinutes())}`,
      },
    })
    fireEvent.click(screen.getByTestId('interview-time-submit'))
    expect(screen.getByTestId('interview-time-error')).toHaveTextContent('面试时间必须是将来时间')
  })

  it('T026 — submitting a future time calls onUpdate with the ISO timestamp', async () => {
    const onUpdate = vi.fn()
    wrap(
      <StatusPopover
        {...baseProps}
        currentStatus="applied"
        onUpdate={onUpdate}
      />,
    )
    fireEvent.click(screen.getByTestId('status-popover-trigger'))
    fireEvent.click(screen.getByTestId('status-menuitem-interview_1'))

    const future = new Date(Date.now() + 48 * 60 * 60 * 1000)
    const pad = (n: number) => String(n).padStart(2, '0')
    const localStr = `${future.getFullYear()}-${pad(future.getMonth() + 1)}-${pad(future.getDate())}T${pad(future.getHours())}:${pad(future.getMinutes())}`
    fireEvent.change(screen.getByTestId('interview-time-input'), {
      target: { value: localStr },
    })
    fireEvent.click(screen.getByTestId('interview-time-submit'))

    await waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1))
    const [target, time] = onUpdate.mock.calls[0] as [string, string]
    expect(target).toBe('interview_1')
    expect(typeof time).toBe('string')
    // The returned string must be a valid ISO datetime.
    expect(() => new Date(time).toISOString()).not.toThrow()
  })

  it('T027 — terminal status renders the disabled popover with tooltip', () => {
    wrap(<StatusPopover {...baseProps} currentStatus="failed" />)
    const disabled = screen.getByTestId('status-popover-disabled')
    expect(disabled).toBeInTheDocument()
    expect(disabled).toHaveAttribute('aria-disabled')
    // The tooltip text lives in the same wrapper.
    expect(screen.getByRole('tooltip')).toHaveTextContent('已终结的岗位无法推进')
    // The regular trigger must NOT be rendered for terminal jobs.
    expect(screen.queryByTestId('status-popover-trigger')).not.toBeInTheDocument()
  })

  it('T027 — non-terminal status does NOT show the disabled affordance', () => {
    wrap(<StatusPopover {...baseProps} currentStatus="applied" />)
    expect(screen.queryByTestId('status-popover-disabled')).not.toBeInTheDocument()
    expect(screen.getByTestId('status-popover-trigger')).toBeInTheDocument()
  })
})

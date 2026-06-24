/**
 * AiOptimizePanel — smoke test.
 *
 * The state machine itself is covered by `useResumeOptimize.test.ts`.
 * This file only verifies that the panel renders the right slots
 * per status and wires the buttons to the hook actions.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const mockStart = vi.fn()
const mockCancel = vi.fn()
const mockApply = vi.fn()
const mockDiscard = vi.fn()
const mockToggle = vi.fn()
const mockAcceptAll = vi.fn()
const mockRejectAll = vi.fn()
const mockReset = vi.fn()

vi.mock('@/modules/resume/hooks/useResumeOptimize', () => ({
  useResumeOptimize: () => ({
    status: 'idle',
    loading: false,
    error: null,
    threadId: null,
    summary: null,
    patches: [],
    acceptedIndices: new Set<number>(),
    versionId: null,
    elapsedSec: 0,
    start: mockStart,
    cancel: mockCancel,
    togglePatch: mockToggle,
    acceptAll: mockAcceptAll,
    rejectAll: mockRejectAll,
    apply: mockApply,
    discard: mockDiscard,
    reset: mockReset,
  }),
}))

import AiOptimizePanel from '../AiOptimizePanel'

describe('AiOptimizePanel — idle state', () => {
  beforeEach(() => {
    mockStart.mockReset()
    mockReset.mockReset()
  })

  it('renders a trigger button', () => {
    render(<AiOptimizePanel branchId="b1" />)
    expect(screen.getByTestId('ai-optimize-btn')).toBeInTheDocument()
    expect(screen.getByText('AI 优化')).toBeInTheDocument()
  })

  it('opens modal on click and shows JD input', () => {
    render(<AiOptimizePanel branchId="b1" />)
    fireEvent.click(screen.getByTestId('ai-optimize-btn'))
    expect(screen.getByTestId('ai-jd-input')).toBeInTheDocument()
    expect(screen.getByTestId('ai-start-btn')).toBeInTheDocument()
  })

  it('start button is disabled when JD is empty', () => {
    render(<AiOptimizePanel branchId="b1" />)
    fireEvent.click(screen.getByTestId('ai-optimize-btn'))
    const startBtn = screen.getByTestId('ai-start-btn')
    expect(startBtn).toBeDisabled()
  })

  it('calls start() with the JD when start button clicked', () => {
    render(<AiOptimizePanel branchId="b1" />)
    fireEvent.click(screen.getByTestId('ai-optimize-btn'))
    fireEvent.change(screen.getByTestId('ai-jd-input'), {
      target: { value: 'Senior frontend engineer JD' },
    })
    fireEvent.click(screen.getByTestId('ai-start-btn'))
    expect(mockStart).toHaveBeenCalledWith({
      branch_id: 'b1',
      target_jd: 'Senior frontend engineer JD',
    })
  })
})

describe('AiOptimizePanel — waiting_patches state', () => {
  beforeEach(() => {
    mockApply.mockReset()
    mockDiscard.mockReset()
    mockAcceptAll.mockReset()
    mockRejectAll.mockReset()
    mockToggle.mockReset()
  })

  it('renders patch rows with checkboxes + bulk buttons + apply/discard', async () => {
    vi.resetModules()
    vi.doMock('@/modules/resume/hooks/useResumeOptimize', () => ({
      useResumeOptimize: () => ({
        status: 'waiting_patches',
        loading: false,
        error: null,
        threadId: 't1',
        summary: '建议补充技能关键词',
        patches: [
          { index: 0, op: 'replace', path: '/blocks/2/content_md', value: '新内容', oldValue: '旧内容' },
          { index: 1, op: 'add', path: '/blocks/5', value: { type: 'skill' }, oldValue: undefined },
        ],
        acceptedIndices: new Set([0, 1]),
        versionId: null,
        elapsedSec: 12,
        start: vi.fn(),
        cancel: vi.fn(),
        togglePatch: mockToggle,
        acceptAll: mockAcceptAll,
        rejectAll: mockRejectAll,
        apply: mockApply,
        discard: mockDiscard,
        reset: vi.fn(),
      }),
    }))
    const { default: Panel } = await import('../AiOptimizePanel')
    render(<Panel branchId="b1" />)
    fireEvent.click(screen.getByTestId('ai-optimize-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-patches')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-patch-0')).toBeInTheDocument()
    expect(screen.getByTestId('ai-patch-1')).toBeInTheDocument()
    expect(screen.getByTestId('ai-accept-all-btn')).toBeInTheDocument()
    expect(screen.getByTestId('ai-reject-all-btn')).toBeInTheDocument()
    expect(screen.getByTestId('ai-apply-btn')).toBeInTheDocument()
    expect(screen.getByTestId('ai-discard-btn')).toBeInTheDocument()
    vi.doUnmock('@/modules/resume/hooks/useResumeOptimize')
    vi.resetModules()
  })

  it('apply button shows the accepted count', async () => {
    vi.resetModules()
    vi.doMock('@/modules/resume/hooks/useResumeOptimize', () => ({
      useResumeOptimize: () => ({
        status: 'waiting_patches',
        loading: false,
        error: null,
        threadId: 't1',
        summary: null,
        patches: [
          { index: 0, op: 'replace', path: '/a', value: '1' },
          { index: 1, op: 'replace', path: '/b', value: '2' },
          { index: 2, op: 'add', path: '/c', value: '3' },
        ],
        acceptedIndices: new Set([0, 2]),
        versionId: null,
        elapsedSec: 5,
        start: vi.fn(),
        cancel: vi.fn(),
        togglePatch: vi.fn(),
        acceptAll: vi.fn(),
        rejectAll: vi.fn(),
        apply: mockApply,
        discard: vi.fn(),
        reset: vi.fn(),
      }),
    }))
    const { default: Panel } = await import('../AiOptimizePanel')
    render(<Panel branchId="b1" />)
    fireEvent.click(screen.getByTestId('ai-optimize-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('ai-apply-btn')).toBeInTheDocument()
    })
    expect(screen.getByTestId('ai-apply-btn').textContent).toContain('(2)')
    vi.doUnmock('@/modules/resume/hooks/useResumeOptimize')
    vi.resetModules()
  })
})

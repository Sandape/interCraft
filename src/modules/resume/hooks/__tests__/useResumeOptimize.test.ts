/**
 * useResumeOptimize — state machine + per-patch + polling backoff.
 *
 * Tests exercise the public hook via a mocked ResumeOptimizeRepository.
 * The repository is injected through the module-level dependency, so we
 * stub `resumeOptimizeRepo` via vi.mock.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

const mockStart = vi.fn()
const mockGetState = vi.fn()
const mockConfirm = vi.fn()

vi.mock('@/modules/resume/repositories/resumeOptimizeRepo', () => ({
  resumeOptimizeRepo: {
    start: (...args: unknown[]) => mockStart(...args),
    getState: (...args: unknown[]) => mockGetState(...args),
    confirm: (...args: unknown[]) => mockConfirm(...args),
  },
}))

// Import after mock so the hook picks up the stub.
const { useResumeOptimize, __testables__ } = await import('../useResumeOptimize')

describe('useResumeOptimize — state machine', () => {
  beforeEach(() => {
    mockStart.mockReset()
    mockGetState.mockReset()
    mockConfirm.mockReset()
  })

  it('initial state is idle with empty patches', () => {
    const { result } = renderHook(() => useResumeOptimize())
    expect(result.current.status).toBe('idle')
    expect(result.current.patches).toEqual([])
    expect(result.current.acceptedIndices.size).toBe(0)
    expect(result.current.error).toBeNull()
  })

  it('start() transitions to polling then to waiting_patches when status flips', async () => {
    mockStart.mockResolvedValue({ thread_id: 't1', status: 'running', current_node: 'load_branch' })
    mockGetState.mockResolvedValue({
      thread_id: 't1',
      status: 'waiting_interrupt',
      current_node: 'apply_or_discard',
      summary: '优化摘要',
      proposed_patches: [
        { op: 'replace', path: '/blocks/2/content_md', value: '新内容' },
        { op: 'add', path: '/blocks/5', value: { type: 'skill' } },
      ],
    })

    const { result } = renderHook(() => useResumeOptimize())

    await act(async () => {
      await result.current.start({ branch_id: 'b1', target_jd: 'JD text' })
    })

    // start() resolves then pollOnce() runs as fire-and-forget microtask.
    await waitFor(() => {
      expect(result.current.status).toBe('waiting_patches')
    })
    expect(result.current.patches).toHaveLength(2)
    expect(result.current.acceptedIndices.size).toBe(2) // default = all
    expect(result.current.summary).toBe('优化摘要')
    expect(result.current.threadId).toBe('t1')
  })

  it('togglePatch flips accepted state', async () => {
    // Setup: jump straight to waiting_patches
    mockStart.mockResolvedValue({ thread_id: 't1', status: 'running', current_node: 'load_branch' })
    mockGetState.mockResolvedValue({
      thread_id: 't1',
      status: 'waiting_interrupt',
      summary: null,
      proposed_patches: [{ op: 'replace', path: '/x', value: 'a' }],
    })

    const { result } = renderHook(() => useResumeOptimize())
    await act(async () => {
      await result.current.start({ branch_id: 'b1' })
    })
    await waitFor(() => expect(result.current.status).toBe('waiting_patches'))

    expect(result.current.acceptedIndices.has(0)).toBe(true)
    act(() => result.current.togglePatch(0))
    expect(result.current.acceptedIndices.has(0)).toBe(false)
    act(() => result.current.togglePatch(0))
    expect(result.current.acceptedIndices.has(0)).toBe(true)
  })

  it('apply() sends null when all accepted, indices when partial', async () => {
    mockStart.mockResolvedValue({ thread_id: 't1', status: 'running' })
    mockGetState.mockResolvedValue({
      thread_id: 't1',
      status: 'waiting_interrupt',
      summary: null,
      proposed_patches: [
        { op: 'replace', path: '/a', value: '1' },
        { op: 'replace', path: '/b', value: '2' },
        { op: 'add', path: '/c', value: '3' },
      ],
    })
    mockConfirm.mockResolvedValue({ thread_id: 't1', status: 'completed', decision: 'apply', version_id: 'v1' })

    const { result } = renderHook(() => useResumeOptimize())
    await act(async () => {
      await result.current.start({ branch_id: 'b1' })
    })
    await waitFor(() => expect(result.current.status).toBe('waiting_patches'))

    // Default: all accepted → indices should be null on apply
    await act(async () => {
      await result.current.apply()
    })
    expect(mockConfirm).toHaveBeenLastCalledWith('t1', 'apply', null)
    expect(result.current.versionId).toBe('v1')
    expect(result.current.status).toBe('done')

    // Now reject index 1, then call apply again
    mockStart.mockResolvedValue({ thread_id: 't2', status: 'running' })
    mockGetState.mockResolvedValue({
      thread_id: 't2',
      status: 'waiting_interrupt',
      summary: null,
      proposed_patches: [
        { op: 'replace', path: '/a', value: '1' },
        { op: 'replace', path: '/b', value: '2' },
        { op: 'add', path: '/c', value: '3' },
      ],
    })

    const { result: r2 } = renderHook(() => useResumeOptimize())
    await act(async () => {
      await r2.current.start({ branch_id: 'b1' })
    })
    await waitFor(() => expect(r2.current.status).toBe('waiting_patches'))

    act(() => {
      r2.current.togglePatch(1)
    })
    await act(async () => {
      await r2.current.apply()
    })
    expect(mockConfirm).toHaveBeenLastCalledWith('t2', 'apply', [0, 2])
  })

  it('discard() sends decision=discard with no indices', async () => {
    mockStart.mockResolvedValue({ thread_id: 't1', status: 'running' })
    mockGetState.mockResolvedValue({
      thread_id: 't1',
      status: 'waiting_interrupt',
      summary: null,
      proposed_patches: [{ op: 'replace', path: '/x', value: 'a' }],
    })
    mockConfirm.mockResolvedValue({ thread_id: 't1', status: 'completed', decision: 'discard', version_id: null })

    const { result } = renderHook(() => useResumeOptimize())
    await act(async () => {
      await result.current.start({ branch_id: 'b1' })
    })
    await waitFor(() => expect(result.current.status).toBe('waiting_patches'))

    await act(async () => {
      await result.current.discard()
    })
    expect(mockConfirm).toHaveBeenLastCalledWith('t1', 'discard', null)
    expect(result.current.status).toBe('done')
    expect(result.current.versionId).toBeNull()
  })

  it('60s budget times out', async () => {
    // Fake timers only here — we need to fast-forward 60s of wall time.
    vi.useFakeTimers()
    try {
      mockStart.mockResolvedValue({ thread_id: 't1', status: 'running' })
      mockGetState.mockResolvedValue({
        thread_id: 't1',
        status: 'running',
        summary: null,
        proposed_patches: null,
      })

      const { result } = renderHook(() => useResumeOptimize())
      await act(async () => {
        await result.current.start({ branch_id: 'b1' })
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(61_000)
      })
      expect(result.current.status).toBe('timeout')
      expect(result.current.error).toContain('60s')
    } finally {
      vi.useRealTimers()
    }
  })

  it('reset() returns to idle', async () => {
    mockStart.mockResolvedValue({ thread_id: 't1', status: 'running' })
    mockGetState.mockResolvedValue({
      thread_id: 't1',
      status: 'running',
      summary: null,
      proposed_patches: null,
    })

    const { result } = renderHook(() => useResumeOptimize())
    await act(async () => {
      await result.current.start({ branch_id: 'b1' })
    })
    expect(result.current.status).toBe('polling')

    act(() => result.current.reset())
    expect(result.current.status).toBe('idle')
    expect(result.current.threadId).toBeNull()
  })
})

describe('useResumeOptimize — helpers', () => {
  it('readAtPath walks object + array paths', () => {
    const blocks = [
      { id: '1', content_md: 'A' },
      { id: '2', content_md: 'B' },
    ]
    expect(__testables__.readAtPath(blocks, '/0/content_md')).toBe('A')
    expect(__testables__.readAtPath(blocks, '/1/content_md')).toBe('B')
    expect(__testables__.readAtPath(blocks, '/2/content_md')).toBeUndefined()
    expect(__testables__.readAtPath(blocks, '')).toBeUndefined()
  })

  it('hydratePatches assigns stable 0-based indices + defaults acceptedIndices to all', () => {
    const raw = [
      { op: 'replace', path: '/blocks/0/content_md', value: 'X' },
      { op: 'replace', path: '/blocks/1/content_md', value: 'Y' },
    ]
    // hydratePatches walks paths starting with /blocks/, so data must be wrapped.
    const blocks = {
      blocks: [
        { content_md: 'old0' },
        { content_md: 'old1' },
      ],
    }
    const { patches, acceptedIndices } = __testables__.hydratePatches(raw, blocks)
    expect(patches).toHaveLength(2)
    expect(patches[0]).toMatchObject({ index: 0, op: 'replace', oldValue: 'old0' })
    expect(patches[1]).toMatchObject({ index: 1, op: 'replace', oldValue: 'old1' })
    expect(acceptedIndices).toEqual(new Set([0, 1]))
  })

  it('hydratePatches with null/empty returns empty', () => {
    expect(__testables__.hydratePatches(null, null)).toEqual({ patches: [], acceptedIndices: new Set() })
    expect(__testables__.hydratePatches([], null)).toEqual({ patches: [], acceptedIndices: new Set() })
  })
})

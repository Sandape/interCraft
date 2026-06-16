/** T055 — useClearErrorQuestionSource mutation + useErrorQuestions source filter. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor, act } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import type { ErrorQuestion } from '@/repositories/ErrorQuestionRepository'

const clearSourceMock = vi.fn()
const listMock = vi.fn()

vi.mock('@/repositories/types', () => ({
  getErrorQuestionRepository: () => ({
    list: listMock,
    get: vi.fn(),
    create: vi.fn(),
    patch: vi.fn(),
    archive: vi.fn(),
    reset: vi.fn(),
    recall: vi.fn(),
    clearSource: clearSourceMock,
  }),
}))

import { useClearErrorQuestionSource } from '@/hooks/mutations/useErrorQuestionMutations'
import { useErrorQuestions } from '@/hooks/queries/useErrorQuestions'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

const MOCK_EQ: ErrorQuestion = {
  id: 'eq-1',
  source_session_id: 'session-1',
  source_question_id: 'sq-1',
  dimension: 'algorithm',
  question_text: 'What is a hash map?',
  answer_text: 'A key-value store',
  reference_answer_md: null,
  status: 'fresh',
  frequency: 3,
  score: 4,
  tags: null,
  archived_at: null,
  last_practiced_at: null,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
}

beforeEach(() => {
  clearSourceMock.mockReset()
  listMock.mockReset()
})

describe('useClearErrorQuestionSource', () => {
  it('calls clearSource on the repository and returns the updated question', async () => {
    clearSourceMock.mockResolvedValue({ ...MOCK_EQ, source_session_id: null, source_question_id: null })

    const { result } = renderHook(() => useClearErrorQuestionSource(), {
      wrapper: createWrapper(),
    })

    let resolved: ErrorQuestion | undefined
    await act(async () => {
      resolved = await result.current.mutateAsync('eq-1')
    })

    expect(clearSourceMock).toHaveBeenCalledWith('eq-1')
    expect(resolved!.source_question_id).toBeNull()
    expect(resolved!.source_session_id).toBeNull()
    expect(resolved!.question_text).toBe('What is a hash map?')
  })

  it('updates the errorQuestions list cache on success', async () => {
    const updated = { ...MOCK_EQ, source_session_id: null, source_question_id: null }
    clearSourceMock.mockResolvedValue(updated)

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
    // Seed the list cache with the original question
    qc.setQueryData(['errorQuestions', {}], {
      data: [MOCK_EQ],
      next_cursor: null,
      has_more: false,
    })

    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: qc }, children)

    const { result } = renderHook(() => useClearErrorQuestionSource(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync('eq-1')
    })

    const cached = qc.getQueryData<{ data: ErrorQuestion[] }>(['errorQuestions', {}])
    expect(cached).not.toBeNull()
    if (cached) {
      const found = cached.data.find((e: ErrorQuestion) => e.id === 'eq-1')
      expect(found).toBeDefined()
      expect(found!.source_question_id).toBeNull()
      expect(found!.source_session_id).toBeNull()
    }
  })

  it('propagates error when clearSource fails', async () => {
    clearSourceMock.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useClearErrorQuestionSource(), {
      wrapper: createWrapper(),
    })

    await act(async () => {
      try {
        await result.current.mutateAsync('eq-1')
      } catch { /* expected */ }
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeDefined()
  })
})

describe('useErrorQuestions — source filter', () => {
  it('passes source=auto to the repository list call', async () => {
    listMock.mockResolvedValue({ data: [MOCK_EQ], next_cursor: null, has_more: false })

    renderHook(() => useErrorQuestions({ source: 'auto' }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith({ source: 'auto' })
    })
  })

  it('passes source=manual to the repository list call', async () => {
    listMock.mockResolvedValue({ data: [], next_cursor: null, has_more: false })

    renderHook(() => useErrorQuestions({ source: 'manual' }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith({ source: 'manual' })
    })
  })

  it('omits source param when not specified', async () => {
    listMock.mockResolvedValue({ data: [], next_cursor: null, has_more: false })

    renderHook(() => useErrorQuestions({ status: 'fresh' }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith({ status: 'fresh' })
      // source should not be in the call
      const callArg = listMock.mock.calls[0][0] as Record<string, unknown>
      expect(callArg).not.toHaveProperty('source')
    })
  })
})

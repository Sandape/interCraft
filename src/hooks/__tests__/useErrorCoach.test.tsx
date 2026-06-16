/** 018 #10 — useErrorCoach should poll thread state after start,
    stop polling on terminal status, and surface errors in Chinese. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

const { startMock, sendMessageMock, abortMock, getStateMock } = vi.hoisted(() => ({
  startMock: vi.fn(),
  sendMessageMock: vi.fn(),
  abortMock: vi.fn(),
  getStateMock: vi.fn(),
}))

vi.mock('@/repositories/errorCoachRepo', () => ({
  errorCoachRepo: {
    start: startMock,
    sendMessage: sendMessageMock,
    abort: abortMock,
    getState: getStateMock,
  },
}))

import { useErrorCoach } from '@/hooks/useErrorCoach'

beforeEach(() => {
  startMock.mockReset()
  sendMessageMock.mockReset()
  abortMock.mockReset()
  getStateMock.mockReset()
})

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useErrorCoach — polling (018 #10)', () => {
  it('start() creates thread and getState is called', async () => {
    startMock.mockResolvedValue({ thread_id: 'th-1', status: 'starting', current_node: null })
    getStateMock.mockResolvedValue({ thread_id: 'th-1', status: 'starting', correct_count: 0, attempt_count: 0, current_hint_level: null })

    const { result } = renderHook(() => useErrorCoach(), { wrapper })

    await act(async () => {
      await result.current.start('eq-1')
    })

    expect(startMock).toHaveBeenCalledWith({ error_question_id: 'eq-1' })
    expect(result.current.threadId).toBe('th-1')
    await waitFor(() => {
      expect(getStateMock).toHaveBeenCalledWith('th-1')
    })
  })

  it('surfaces terminal status from getState', async () => {
    startMock.mockResolvedValue({ thread_id: 'th-2', status: 'running', current_node: 'question_gen' })
    getStateMock.mockResolvedValue({ thread_id: 'th-2', status: 'completed', correct_count: 3, attempt_count: 3, current_hint_level: null })

    const { result } = renderHook(() => useErrorCoach(), { wrapper })

    await act(async () => {
      await result.current.start('eq-1')
    })

    await waitFor(() => {
      expect(result.current.status).toBe('completed')
    })
    expect(result.current.correctCount).toBe(3)
  })

  it('submitAnswer calls sendMessage', async () => {
    startMock.mockResolvedValue({ thread_id: 'th-4', status: 'running', current_node: 'score' })
    getStateMock.mockResolvedValue({ thread_id: 'th-4', status: 'running', correct_count: 1, attempt_count: 1, current_hint_level: null })
    sendMessageMock.mockResolvedValue({ thread_id: 'th-4', status: 'running', score: 8, correct_count: 2, current_node: null, hint_level: null, hint_content: null })

    const { result } = renderHook(() => useErrorCoach(), { wrapper })

    await act(async () => {
      await result.current.start('eq-1')
    })

    await act(async () => {
      await result.current.submitAnswer('my answer')
    })

    expect(sendMessageMock).toHaveBeenCalledWith('th-4', 'my answer')
  })

  it('start failure surfaces error and loading becomes false', async () => {
    startMock.mockRejectedValue(new Error('启动超时，请重试'))

    const { result } = renderHook(() => useErrorCoach(), { wrapper })

    await act(async () => {
      try {
        await result.current.start('eq-1')
      } catch { /* expected */ }
    })

    expect(result.current.error).toBe('启动超时，请重试')
    expect(result.current.loading).toBe(false)
  })
})
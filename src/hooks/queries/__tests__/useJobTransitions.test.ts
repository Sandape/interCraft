import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createElement, type ReactNode } from 'react'

vi.mock('@/api/jobs', () => ({
  getJobTransitions: vi.fn(),
}))

import { useJobTransitions } from '@/hooks/queries/useJobTransitions'
import { getJobTransitions } from '@/api/jobs'

const mockedGet = vi.mocked(getJobTransitions)

const KNOWN_GRAPH = {
  statuses: ['applied', 'test', 'oa', 'hr', 'offer', 'rejected', 'withdrawn'],
  transitions: [
    { from: 'applied', to: 'test' },
    { from: 'applied', to: 'rejected' },
    { from: 'test', to: 'rejected' },
  ],
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useJobTransitions', () => {
  beforeEach(() => {
    mockedGet.mockReset()
  })

  it('returns 7 statuses from the API when the fetch succeeds', async () => {
    mockedGet.mockResolvedValue(KNOWN_GRAPH)
    const { result } = renderHook(() => useJobTransitions(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(mockedGet).toHaveBeenCalled())
    await waitFor(() => expect(result.current.data.statuses).toEqual(KNOWN_GRAPH.statuses))
    expect(result.current.data.transitions).toEqual(KNOWN_GRAPH.transitions)
    expect(result.current.isStale).toBe(false)
    expect(result.current.isLoading).toBe(false)
  })

  it('falls back to a non-null 7-status graph when the fetch rejects', async () => {
    mockedGet.mockRejectedValue(new Error('network down'))
    const { result } = renderHook(() => useJobTransitions(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(mockedGet).toHaveBeenCalled())
    // The hook uses retry: 1 with exponential backoff; allow up to 5s for the
    // query to settle into the error state.
    await waitFor(() => expect(result.current.isStale).toBe(true), { timeout: 5000 })
    expect(result.current.data).not.toBeNull()
    expect(result.current.data.statuses).toHaveLength(7)
    expect(result.current.data.transitions).toHaveLength(20)
    for (const s of ['applied', 'test', 'oa', 'hr', 'offer', 'rejected', 'withdrawn']) {
      expect(result.current.data.statuses).toContain(s)
    }
  })
})

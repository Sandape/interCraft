import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useGlobalSearch } from '@/hooks/queries/useGlobalSearch'
import { searchApi } from '@/api/search'

vi.mock('@/api/search', () => ({
  searchApi: {
    search: vi.fn(),
  },
}))

const mockedSearch = vi.mocked(searchApi.search)

const resultPayload = {
  groups: [
    {
      type: 'resume' as const,
      label: 'Resume branches',
      total: 1,
      items: [
        {
          id: 'branch-1',
          type: 'resume' as const,
          title: 'Target resume',
          subtitle: 'Frontend',
          destination: '/resume/branch-1',
          score: 1,
          meta: {},
        },
      ],
    },
  ],
  query: 'target',
  took_ms: 12,
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

describe('useGlobalSearch', () => {
  beforeEach(() => {
    mockedSearch.mockReset()
  })

  it('does not request for whitespace-only input and resets to idle', async () => {
    const { result } = renderHook(() => useGlobalSearch())

    act(() => result.current.setQuery('   '))
    await sleep(250)

    expect(mockedSearch).not.toHaveBeenCalled()
    expect(result.current.requestState).toBe('idle')
    expect(result.current.groups).toEqual([])
  })

  it('debounces requests and truncates query text to 200 characters', async () => {
    mockedSearch.mockResolvedValue(resultPayload)
    const { result } = renderHook(() => useGlobalSearch())
    const longQuery = ` ${'a'.repeat(240)} `

    act(() => result.current.setQuery(longQuery))
    await sleep(150)
    expect(mockedSearch).not.toHaveBeenCalled()

    await waitFor(() => expect(result.current.requestState).toBe('success'))
    expect(mockedSearch).toHaveBeenCalledTimes(1)
    expect(mockedSearch.mock.calls[0][0]).toBe('a'.repeat(200))
    expect(result.current.groups).toEqual(resultPayload.groups)
  })

  it('aborts the previous in-flight request and renders the latest response', async () => {
    const signals: AbortSignal[] = []
    mockedSearch.mockImplementation((query, signal) => {
      signals.push(signal!)
      return new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            groups: [
              {
                ...resultPayload.groups[0],
                items: [
                  {
                    ...resultPayload.groups[0].items[0],
                    id: `branch-${query}`,
                    title: `Result ${query}`,
                  },
                ],
              },
            ],
            query,
            took_ms: 1,
          })
        }, query === 'first' ? 80 : 10)
      })
    })

    const { result } = renderHook(() => useGlobalSearch())

    act(() => result.current.setQuery('first'))

    await waitFor(() => expect(mockedSearch).toHaveBeenCalledTimes(1))

    act(() => result.current.setQuery('second'))

    await waitFor(() => expect(mockedSearch).toHaveBeenCalledTimes(2))
    expect(signals[0].aborted).toBe(true)

    await waitFor(() => expect(result.current.groups[0].items[0].id).toBe('branch-second'))

    await sleep(100)
    expect(result.current.groups[0].items[0].id).toBe('branch-second')
  })

  it('surfaces a retryable error state when the request fails', async () => {
    mockedSearch
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(resultPayload)
    const { result } = renderHook(() => useGlobalSearch())

    act(() => result.current.setQuery('target'))

    await waitFor(() => expect(result.current.requestState).toBe('error'))
    expect(result.current.error).toBeTruthy()
    expect(result.current.groups).toEqual([])

    await act(async () => {
      result.current.retry()
    })

    await waitFor(() => expect(result.current.requestState).toBe('success'))
    expect(result.current.groups).toEqual(resultPayload.groups)
  })
})

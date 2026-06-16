/**
 * useGlobalSearch — debounce + truncate + AbortController.
 *
 * - Truncates input to 200 chars before sending (FR-013).
 * - 200 ms debounce so we don't fire on every keystroke.
 * - AbortController cancels the previous request when a new one starts
 *   so only the latest response renders (D3 / FR-011).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { searchApi } from '@/api/search'
import type { SearchGroup, SearchRequestState } from '@/types/search'

const DEBOUNCE_MS = 200
const MAX_QUERY_LENGTH = 200

export function useGlobalSearch() {
  const [query, setQuery] = useState('')
  const [groups, setGroups] = useState<SearchGroup[]>([])
  const [requestState, setRequestState] = useState<SearchRequestState>('idle')
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSuccessfulQueryRef = useRef('')

  const runFetch = useCallback(async (q: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setRequestState('loading')
    setError(null)
    try {
      const res = await searchApi.search(q, controller.signal)
      if (controller.signal.aborted) return
      setGroups(res.groups)
      setRequestState('success')
      lastSuccessfulQueryRef.current = q
    } catch (err) {
      if (controller.signal.aborted) return
      // Distinguish abort from real errors.
      const e = err as { name?: string; message?: string }
      if (e?.name === 'AbortError' || e?.name === 'CanceledError') return
      setRequestState('error')
      setError('搜索失败，请稍后重试')
      setGroups([])
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    const trimmed = query.trim()
    if (trimmed.length === 0) {
      abortRef.current?.abort()
      setGroups([])
      setRequestState('idle')
      setError(null)
      return
    }
    debounceRef.current = setTimeout(() => {
      const truncated = trimmed.slice(0, MAX_QUERY_LENGTH)
      void runFetch(truncated)
    }, DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
    }
  }, [query, runFetch])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const retry = useCallback(() => {
    const trimmed = query.trim()
    if (trimmed.length === 0) return
    void runFetch(trimmed.slice(0, MAX_QUERY_LENGTH))
  }, [query, runFetch])

  return {
    query,
    setQuery,
    groups,
    requestState,
    error,
    retry,
    lastSuccessfulQuery: lastSuccessfulQueryRef.current,
  }
}

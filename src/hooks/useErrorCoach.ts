/** useErrorCoach — M17 Error Coach flow with React Query polling.

  After start() creates a thread, we poll GET .../state every 1.5 s
  until status reaches a terminal value (completed / error / aborted),
  then polling auto-stops.
*/

import { useCallback, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { errorCoachRepo, type MessageResponse } from '../repositories/errorCoachRepo'
import { coachErrorToMessage } from '../lib/apiErrorToMessage'
import type { StateResponse } from '../repositories/errorCoachRepo'

export interface ErrorCoachState {
  loading: boolean
  error: string | null
  threadId: string | null
  status: string | null
  correctCount: number
  attemptCount: number
  hintLevel: string | null
  hintContent: string | null
  score: number | null
}

function threadQueryKey(threadId: string | null) {
  return ['errorCoach', 'state', threadId] as const
}

export function useErrorCoach() {
  const [threadId, setThreadId] = useState<string | null>(null)
  const [manualError, setManualError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const isTerminal = (s: string | null | undefined) =>
    s === 'completed' || s === 'error' || s === 'aborted'

  // Poll state while a non-terminal thread exists
  const stateQuery = useQuery({
    queryKey: threadQueryKey(threadId),
    queryFn: () => errorCoachRepo.getState(threadId!),
    enabled: !!threadId,
    refetchInterval: (query) => {
      const s = (query.state.data as StateResponse | undefined)?.status
      if (!s || isTerminal(s)) return false
      return 1500
    },
    staleTime: 0,
  })

  const start = useCallback(async (errorQuestionId: string) => {
    setManualError(null)
    try {
      const res = await errorCoachRepo.start({ error_question_id: errorQuestionId })
      setThreadId(res.thread_id)
      return res
    } catch (err) {
      setManualError(coachErrorToMessage(err))
      throw err
    }
  }, [])

  const submitAnswer = useCallback(async (content: string): Promise<MessageResponse | null> => {
    if (!threadId) return null
    try {
      const res = await errorCoachRepo.sendMessage(threadId, content)
      // Invalidate so polling immediately picks up new state
      queryClient.invalidateQueries({ queryKey: threadQueryKey(threadId) })
      return res
    } catch (err) {
      setManualError(coachErrorToMessage(err))
      return null
    }
  }, [threadId, queryClient])

  const abort = useCallback(async () => {
    if (!threadId) return
    try {
      await errorCoachRepo.abort(threadId)
      queryClient.setQueryData(threadQueryKey(threadId), {
        thread_id: threadId,
        status: 'aborted',
        correct_count: stateQuery.data?.correct_count ?? 0,
        attempt_count: stateQuery.data?.attempt_count ?? 0,
        current_hint_level: null,
      })
    } catch {
      // Swallow abort errors
    }
  }, [threadId, stateQuery.data, queryClient])

  const reset = useCallback(() => {
    setThreadId(null)
    setManualError(null)
  }, [])

  const loading = !!threadId && stateQuery.isFetching && !isTerminal(stateQuery.data?.status)
  const error = manualError
    ?? (stateQuery.error ? coachErrorToMessage(stateQuery.error) : null)
    ?? null

  return {
    loading,
    error,
    threadId,
    status: stateQuery.data?.status ?? null,
    correctCount: stateQuery.data?.correct_count ?? 0,
    attemptCount: stateQuery.data?.attempt_count ?? 0,
    hintLevel: stateQuery.data?.current_hint_level ?? null,
    hintContent: null, // only populated from sendMessage response, not from state
    score: null, // only populated from sendMessage response
    start,
    submitAnswer,
    abort,
    reset,
  }
}
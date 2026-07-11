/** useErrorCoach — REQ-061 T088 canonical task state / milestones / cancel-resume. */

import { useCallback, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { errorCoachRepo, type MessageResponse, type StateResponse } from '../repositories/errorCoachRepo'
import { coachErrorToMessage } from '../lib/apiErrorToMessage'

function threadQueryKey(threadId: string | null) {
  return ['errorCoach', 'state', threadId] as const
}

const DOMAIN_TERMINAL = new Set(['completed', 'error', 'aborted', 'failed', 'cancelled', 'succeeded'])
const CANONICAL_TERMINAL = new Set([
  'succeeded',
  'partially_succeeded',
  'failed',
  'cancelled',
  'expired',
])

export function useErrorCoach() {
  const [threadId, setThreadId] = useState<string | null>(null)
  const [manualError, setManualError] = useState<string | null>(null)
  const [lastScore, setLastScore] = useState<number | null>(null)
  const [lastHint, setLastHint] = useState<{ level: string | null; content: string | null }>({
    level: null,
    content: null,
  })
  const queryClient = useQueryClient()

  const isTerminal = (data: StateResponse | undefined) => {
    if (!data) return false
    if (data.terminal === true) return true
    if (data.canonical_status && CANONICAL_TERMINAL.has(data.canonical_status)) return true
    return DOMAIN_TERMINAL.has(data.status)
  }

  const stateQuery = useQuery({
    queryKey: threadQueryKey(threadId),
    queryFn: () => errorCoachRepo.getState(threadId!),
    enabled: !!threadId,
    refetchInterval: (query) => {
      const data = query.state.data as StateResponse | undefined
      if (!data || isTerminal(data)) return false
      return 1500
    },
    staleTime: 0,
  })

  const start = useCallback(async (errorQuestionId: string) => {
    setManualError(null)
    setLastScore(null)
    setLastHint({ level: null, content: null })
    try {
      const res = await errorCoachRepo.start({ error_question_id: errorQuestionId })
      setThreadId(res.thread_id)
      queryClient.setQueryData(threadQueryKey(res.thread_id), {
        thread_id: res.thread_id,
        status: res.status,
        correct_count: 0,
        attempt_count: 0,
        current_hint_level: null,
        task_id: res.task_id ?? null,
        available_actions: res.available_actions ?? ['cancel'],
        milestones: res.milestones ?? [],
      } satisfies StateResponse)
      return res
    } catch (err) {
      setManualError(coachErrorToMessage(err))
      throw err
    }
  }, [queryClient])

  const submitAnswer = useCallback(async (content: string): Promise<MessageResponse | null> => {
    if (!threadId) return null
    try {
      const res = await errorCoachRepo.sendMessage(threadId, content)
      if (res.score != null) setLastScore(res.score)
      setLastHint({ level: res.hint_level, content: res.hint_content })
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
        ...(stateQuery.data ?? {
          thread_id: threadId,
          correct_count: 0,
          attempt_count: 0,
          current_hint_level: null,
        }),
        thread_id: threadId,
        status: 'aborted',
        canonical_status: 'cancelled',
        terminal: true,
        available_actions: [],
      })
    } catch {
      // Swallow abort errors
    }
  }, [threadId, stateQuery.data, queryClient])

  const resume = useCallback(async () => {
    if (!threadId) return
    try {
      const st = await errorCoachRepo.resume(threadId)
      queryClient.setQueryData(threadQueryKey(threadId), st)
    } catch (err) {
      setManualError(coachErrorToMessage(err))
    }
  }, [threadId, queryClient])

  const reset = useCallback(() => {
    setThreadId(null)
    setManualError(null)
    setLastScore(null)
    setLastHint({ level: null, content: null })
  }, [])

  const data = stateQuery.data
  const terminal = isTerminal(data)
  const loading = !!threadId && stateQuery.isFetching && !terminal
  const error = manualError
    ?? (stateQuery.error ? coachErrorToMessage(stateQuery.error) : null)
    ?? null

  return {
    loading,
    error,
    threadId,
    taskId: data?.task_id ?? null,
    status: data?.status ?? null,
    canonicalStatus: data?.canonical_status ?? data?.status ?? null,
    terminal,
    availableActions: data?.available_actions ?? [],
    milestones: data?.milestones ?? [],
    correctCount: data?.correct_count ?? 0,
    attemptCount: data?.attempt_count ?? 0,
    hintLevel: lastHint.level ?? data?.current_hint_level ?? null,
    hintContent: lastHint.content,
    score: lastScore,
    start,
    submitAnswer,
    abort,
    cancel: abort,
    resume,
    reset,
  }
}

/** useErrorCoach — React hook for M17 Error Coach flow. */
import { useCallback, useState } from 'react'
import { errorCoachRepo, type MessageResponse } from '../repositories/errorCoachRepo'

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

export function useErrorCoach() {
  const [state, setState] = useState<ErrorCoachState>({
    loading: false,
    error: null,
    threadId: null,
    status: null,
    correctCount: 0,
    attemptCount: 0,
    hintLevel: null,
    hintContent: null,
    score: null,
  })

  const start = useCallback(async (errorQuestionId: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    try {
      const res = await errorCoachRepo.start({ error_question_id: errorQuestionId })
      setState(prev => ({
        ...prev,
        loading: false,
        threadId: res.thread_id,
        status: res.status,
      }))
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to start',
      }))
    }
  }, [])

  const submitAnswer = useCallback(async (content: string): Promise<MessageResponse | null> => {
    const { threadId } = state
    if (!threadId) return null
    setState(prev => ({ ...prev, loading: true }))
    try {
      const res = await errorCoachRepo.sendMessage(threadId, content)
      setState(prev => ({
        ...prev,
        loading: false,
        status: res.status,
        correctCount: res.correct_count ?? prev.correctCount,
        attemptCount: res.correct_count ?? prev.attemptCount,
        hintLevel: res.hint_level,
        hintContent: res.hint_content,
        score: res.score,
      }))
      return res
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to submit',
      }))
      return null
    }
  }, [state.threadId])

  const abort = useCallback(async () => {
    const { threadId } = state
    if (!threadId) return
    try {
      await errorCoachRepo.abort(threadId)
      setState(prev => ({ ...prev, status: 'aborted' }))
    } catch {
      // Swallow abort errors
    }
  }, [state.threadId])

  const reset = useCallback(() => {
    setState({
      loading: false,
      error: null,
      threadId: null,
      status: null,
      correctCount: 0,
      attemptCount: 0,
      hintLevel: null,
      hintContent: null,
      score: null,
    })
  }, [])

  return { ...state, start, submitAnswer, abort, reset }
}

/** useGeneralCoach — React hook for M19 General Coach. */
import { useCallback, useState } from 'react'
import { generalCoachRepo, type MessageResponse } from '../repositories/generalCoachRepo'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface GeneralCoachState {
  loading: boolean
  error: string | null
  threadId: string | null
  messages: ChatMessage[]
  detectedIntent: string | null
  confidence: number | null
  redirectTo: string | null
  sessionActive: boolean
}

export function useGeneralCoach() {
  const [state, setState] = useState<GeneralCoachState>({
    loading: false,
    error: null,
    threadId: null,
    messages: [],
    detectedIntent: null,
    confidence: null,
    redirectTo: null,
    sessionActive: false,
  })

  const start = useCallback(async (initialQuestion?: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    try {
      const res = await generalCoachRepo.start({ initial_question: initialQuestion || null })
      const initialMessages: ChatMessage[] = initialQuestion
        ? [{ role: 'user', content: initialQuestion }]
        : []

      setState(prev => ({
        ...prev,
        loading: false,
        threadId: res.thread_id,
        messages: initialMessages,
        sessionActive: true,
      }))

      // If there was an initial question, get the response
      if (initialQuestion && res.thread_id) {
        await sendMessage(initialQuestion, res.thread_id)
      }
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to start conversation',
      }))
    }
  }, [])

  const sendMessage = useCallback(async (content: string, overrideThreadId?: string): Promise<MessageResponse | null> => {
    const threadId = overrideThreadId ?? state.threadId
    if (!threadId) return null

    setState(prev => ({
      ...prev,
      loading: true,
      messages: [...prev.messages, { role: 'user', content }],
    }))

    try {
      const res = await generalCoachRepo.sendMessage(threadId, content)
      setState(prev => ({
        ...prev,
        loading: false,
        detectedIntent: res.detected_intent,
        confidence: res.confidence,
        redirectTo: res.redirect_to,
      }))
      return res
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to send message',
      }))
      return null
    }
  }, [state.threadId])

  const close = useCallback(async () => {
    const { threadId } = state
    if (!threadId) return
    try {
      await generalCoachRepo.close(threadId)
    } catch {
      // Swallow close errors
    }
    setState(prev => ({ ...prev, sessionActive: false }))
  }, [state.threadId])

  const reset = useCallback(() => {
    setState({
      loading: false,
      error: null,
      threadId: null,
      messages: [],
      detectedIntent: null,
      confidence: null,
      redirectTo: null,
      sessionActive: false,
    })
  }, [])

  return { ...state, start, sendMessage, close, reset }
}

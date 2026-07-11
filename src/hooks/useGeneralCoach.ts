/** useGeneralCoach — REQ-061 T087 persisted answers + server actions. */
import { useCallback, useState } from 'react'
import { generalCoachRepo, type MessageResponse } from '../repositories/generalCoachRepo'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  feedback?: 'up' | 'down' | null
  turnIndex?: number
}

export interface GeneralCoachState {
  loading: boolean
  error: string | null
  threadId: string | null
  taskId: string | null
  messages: ChatMessage[]
  detectedIntent: string | null
  confidence: number | null
  redirectTo: string | null
  sessionActive: boolean
  availableActions: string[]
  pointSummary: { quoted_max?: number; reserved?: number; settled?: number } | null
  canonicalStatus: string | null
}

function assistantText(res: MessageResponse): string | null {
  return res.assistant_body ?? res.assistant_message ?? res.reply ?? null
}

export function useGeneralCoach() {
  const [state, setState] = useState<GeneralCoachState>({
    loading: false,
    error: null,
    threadId: null,
    taskId: null,
    messages: [],
    detectedIntent: null,
    confidence: null,
    redirectTo: null,
    sessionActive: false,
    availableActions: [],
    pointSummary: null,
    canonicalStatus: null,
  })

  const sendMessage = useCallback(async (content: string, overrideThreadId?: string): Promise<MessageResponse | null> => {
    const threadId = overrideThreadId ?? state.threadId
    if (!threadId) return null

    setState((prev) => ({
      ...prev,
      loading: true,
      messages: [...prev.messages, { role: 'user', content }],
    }))

    try {
      const res = await generalCoachRepo.sendMessage(threadId, content)
      const body = assistantText(res)
      setState((prev) => ({
        ...prev,
        loading: false,
        detectedIntent: res.detected_intent,
        confidence: res.confidence,
        redirectTo: res.redirect_to,
        taskId: res.task_id ?? prev.taskId,
        availableActions: res.available_actions ?? prev.availableActions,
        pointSummary: res.point_summary ?? prev.pointSummary,
        messages: body
          ? [
              ...prev.messages,
              {
                role: 'assistant',
                content: body,
                turnIndex: prev.messages.filter((m) => m.role === 'assistant').length,
              },
            ]
          : prev.messages,
      }))
      return res
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to send message',
      }))
      return null
    }
  }, [state.threadId])

  const start = useCallback(async (initialQuestion?: string) => {
    setState((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const res = await generalCoachRepo.start({ initial_question: initialQuestion || null })
      const initialMessages: ChatMessage[] = initialQuestion
        ? [{ role: 'user', content: initialQuestion }]
        : []

      setState((prev) => ({
        ...prev,
        loading: false,
        threadId: res.thread_id,
        taskId: res.task_id ?? null,
        messages: initialMessages,
        sessionActive: true,
        availableActions: res.available_actions ?? ['cancel'],
        pointSummary: res.point_summary ?? null,
        canonicalStatus: res.status ?? 'running',
      }))

      if (initialQuestion && res.thread_id) {
        await sendMessage(initialQuestion, res.thread_id)
      }
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to start conversation',
      }))
    }
  }, [sendMessage])

  const recover = useCallback(async () => {
    const { threadId } = state
    if (!threadId) return
    setState((prev) => ({ ...prev, loading: true, error: null }))
    try {
      const st = await generalCoachRepo.getState(threadId)
      const persisted = (st.persisted_messages ?? []).map((m, idx) => ({
        role: (m.role === 'assistant' ? 'assistant' : 'user') as 'user' | 'assistant',
        content: String(m.body ?? m.content ?? ''),
        turnIndex: m.role === 'assistant' ? idx : undefined,
      }))
      setState((prev) => ({
        ...prev,
        loading: false,
        messages: persisted.length ? persisted : prev.messages,
        sessionActive: Boolean(st.session_active),
        taskId: st.task_id ?? prev.taskId,
        availableActions: st.available_actions ?? prev.availableActions,
        pointSummary: st.point_summary ?? prev.pointSummary,
        canonicalStatus: st.canonical_status ?? prev.canonicalStatus,
      }))
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : '恢复失败',
      }))
    }
  }, [state.threadId])

  const submitFeedback = useCallback(async (turnIndex: number, rating: 'up' | 'down') => {
    const { threadId } = state
    if (!threadId) return
    try {
      await generalCoachRepo.submitFeedback(threadId, { turn_index: turnIndex, rating })
      setState((prev) => ({
        ...prev,
        messages: prev.messages.map((m) =>
          m.role === 'assistant' && m.turnIndex === turnIndex ? { ...m, feedback: rating } : m,
        ),
      }))
    } catch {
      // feedback is best-effort
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
    setState((prev) => ({ ...prev, sessionActive: false, availableActions: [] }))
  }, [state.threadId])

  const reset = useCallback(() => {
    setState({
      loading: false,
      error: null,
      threadId: null,
      taskId: null,
      messages: [],
      detectedIntent: null,
      confidence: null,
      redirectTo: null,
      sessionActive: false,
      availableActions: [],
      pointSummary: null,
      canonicalStatus: null,
    })
  }, [])

  return { ...state, start, sendMessage, close, reset, recover, submitFeedback }
}

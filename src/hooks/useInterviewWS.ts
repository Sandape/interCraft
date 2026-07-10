/** WebSocket client hook for interview streaming (T035).

Handles:
- Connect to /api/v1/ws/interview?token=...
- Auto-reconnect with exponential backoff (1s/2s/4s/8s/16s, max 5)
- Carries last_seen_checkpoint_id on reconnect
- Event dispatcher: parses JSON events → updates state
- Partial token discard on disconnect

020 (FIX-011, D-008) — when `import.meta.env.VITE_USE_MOCK === 'true'`,
`connect()` short-circuits and feeds the WS event stream from
`useInterviewWS.mock.ts` (sourced from `tests/e2e/fixtures/mock-llm.ts`).
This lets the 5-round interview run end-to-end without a live LLM key.
*/
import { useRef, useState, useCallback, useEffect } from 'react'
import { buildMockEvents, mockInitialState } from './useInterviewWS.mock'

export interface WSEvent {
  type: string
  event_id: string
  session_id: string
  timestamp: string
  node_name: string
  payload: Record<string, any>
}

export type InterviewTurnPhase = 'idle' | 'scoring' | 'awaiting_question' | 'generating_question'

export interface InterviewWSState {
  connected: boolean
  reconnecting: boolean
  reconnectAttempt: number
  currentNode: string | null
  currentQuestion: number
  totalQuestions: number
  streamingText: string
  lastCheckpointId: string | null
  error: WSEvent | null
  events: WSEvent[]
  /** REQ-058 — score may arrive before the next question finishes generating. */
  turnPhase: InterviewTurnPhase
}

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BACKOFF = [1000, 2000, 4000, 8000, 16000]

// 020 (FIX-011, D-008) — read mock-mode from import.meta.env.
// Tests override by mutating `__VITE_USE_MOCK_OVERRIDE__` (see below).
function isMockMode(): boolean {
  const override = (globalThis as any).__VITE_USE_MOCK_OVERRIDE__
  if (typeof override === 'string') return override === 'true'
  return (import.meta as any).env?.VITE_USE_MOCK === 'true'
}

export function useInterviewWS(token: string) {
  // 020 (FIX-011, D-008) — mock-mode short-circuit. We allocate the real
  // refs/state below anyway (cheap) and override `connect` and the event
  // source in mock mode.
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const reconnectCountRef = useRef(0)
  const lastCheckpointRef = useRef<string | null>(null)

  const [state, setState] = useState<InterviewWSState>(() =>
    isMockMode() ? { ...mockInitialState(), turnPhase: 'idle' as InterviewTurnPhase } : {
      connected: false,
      reconnecting: false,
      reconnectAttempt: 0,
      currentNode: null,
      currentQuestion: 0,
      totalQuestions: 5,
      streamingText: '',
      lastCheckpointId: null,
      error: null,
      events: [],
      turnPhase: 'idle',
    },
  )

  const applyTurnPhaseFromEvent = useCallback((parsed: WSEvent, prev: InterviewWSState): InterviewTurnPhase | undefined => {
    if (parsed.type === 'node.started') {
      if (parsed.node_name === 'score') return 'scoring'
      if (parsed.node_name === 'question_gen') return 'generating_question'
      return undefined
    }
    if (parsed.type === 'node.completed') {
      if (parsed.node_name === 'score' && parsed.payload.summary?.score > 0) {
        return 'awaiting_question'
      }
      if (parsed.node_name === 'question_gen' && parsed.payload.summary?.question) {
        return 'idle'
      }
      if (parsed.payload.summary?.overall_score !== undefined) {
        return 'idle'
      }
      return undefined
    }
    if (parsed.type === 'error') {
      return 'idle'
    }
    if (parsed.type === 'plan.status') {
      return prev.turnPhase
    }
    return undefined
  }, [])

  // Reuse the same event-dispatch reducer for both real and mock streams.
  const applyEvent = useCallback((parsed: WSEvent) => {
    setState(prev => {
      const updates: Partial<InterviewWSState> = {
        events: [...prev.events, parsed],
      }
      const nextTurnPhase = applyTurnPhaseFromEvent(parsed, prev)
      if (nextTurnPhase !== undefined) {
        updates.turnPhase = nextTurnPhase
      }
      switch (parsed.type) {
        case 'node.started':
          updates.currentNode = parsed.node_name
          if (parsed.payload.current_question !== undefined) {
            updates.currentQuestion = parsed.payload.current_question
          }
          if (parsed.node_name === 'question_gen') {
            updates.streamingText = ''
          }
          break
        case 'token.delta':
          updates.streamingText = prev.streamingText + (parsed.payload.content || '')
          break
        case 'node.completed':
          updates.lastCheckpointId = parsed.payload.checkpoint_id || null
          if (parsed.payload.checkpoint_id) {
            lastCheckpointRef.current = parsed.payload.checkpoint_id
          }
          if (parsed.payload.summary?.overall_score !== undefined) {
            updates.currentNode = 'completed'
          }
          break
        case 'error':
          updates.error = parsed
          updates.turnPhase = 'idle'
          break
      }
      return { ...prev, ...updates }
    })
  }, [applyTurnPhaseFromEvent])

  const connect = useCallback(() => {
    if (isMockMode()) {
      // 020 (FIX-011, D-008) — feed the full event stream from
      // MOCK_ROUNDS synchronously. No real WebSocket is opened.
      // We compose the entire transition into a single setState so the
      // `connected: true` flag is not overwritten by the subsequent
      // per-event applyEvent updates.
      const events = buildMockEvents()
      setState(prev => {
        let next: InterviewWSState = { ...prev, connected: true, error: null, events: [...prev.events, ...events] }
        // Walk the events so currentNode / lastCheckpointId / etc. reflect
        // the final round (mimics the real reducer in applyEvent).
        for (const parsed of events) {
          const updates: Partial<InterviewWSState> = {}
          const nextTurnPhase = applyTurnPhaseFromEvent(parsed, next)
          if (nextTurnPhase !== undefined) {
            updates.turnPhase = nextTurnPhase
          }
          switch (parsed.type) {
            case 'node.started':
              updates.currentNode = parsed.node_name
              if (parsed.payload.current_question !== undefined) {
                updates.currentQuestion = parsed.payload.current_question
              }
              if (parsed.node_name === 'question_gen') {
                updates.streamingText = ''
              }
              break
            case 'node.completed':
              updates.lastCheckpointId = parsed.payload.checkpoint_id || null
              if (parsed.payload.checkpoint_id) {
                lastCheckpointRef.current = parsed.payload.checkpoint_id
              }
              if (parsed.payload.summary?.overall_score !== undefined) {
                updates.currentNode = 'completed'
              }
              break
            case 'error':
              updates.error = parsed
              updates.turnPhase = 'idle'
              break
          }
          next = { ...next, ...updates }
        }
        return next
      })
      return
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = location.host
    const url = `${protocol}//${host}/api/v1/ws/interview?token=${encodeURIComponent(token)}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setState(prev => ({
        ...prev,
        connected: true,
        reconnecting: false,
        reconnectAttempt: 0,
        error: null,
      }))
      reconnectCountRef.current = 0

      // Send reconnect message if we have a checkpoint
      if (lastCheckpointRef.current) {
        ws.send(JSON.stringify({
          type: 'reconnect',
          session_id: '',
          last_seen_checkpoint_id: lastCheckpointRef.current,
        }))
      }
    }

    ws.onmessage = (event) => {
      try {
        applyEvent(JSON.parse(event.data))
      } catch {
        // Ignore non-JSON messages
      }
    }

    ws.onclose = () => {
      setState(prev => ({ ...prev, connected: false }))
      wsRef.current = null

      // Auto-reconnect
      if (reconnectCountRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = RECONNECT_BACKOFF[reconnectCountRef.current]
        reconnectCountRef.current++
        setState(prev => ({
          ...prev,
          reconnecting: true,
          reconnectAttempt: reconnectCountRef.current,
        }))
        reconnectTimerRef.current = window.setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [token, applyEvent, applyTurnPhaseFromEvent])

  const disconnect = useCallback(() => {
    if (isMockMode()) {
      setState(prev => ({ ...prev, connected: false, reconnecting: false }))
      return
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
    }
    reconnectTimerRef.current = MAX_RECONNECT_ATTEMPTS // prevent reconnect
    wsRef.current?.close()
    wsRef.current = null
    setState(prev => ({ ...prev, connected: false, reconnecting: false }))
  }, [])

  const send = useCallback((msg: Record<string, any>) => {
    if (isMockMode()) {
      // Mock stream is one-way; submitAnswer events are no-ops in mock mode.
      return
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  const submitAnswer = useCallback((sessionId: string, content: string, sequenceNo: number) => {
    setState(prev => ({ ...prev, turnPhase: 'scoring', streamingText: '' }))
    send({
      type: 'submit_answer',
      session_id: sessionId,
      content,
      sequence_no: sequenceNo,
    })
  }, [send])

  const reconnect = useCallback((sessionId: string, lastCheckpointId?: string) => {
    send({
      type: 'reconnect',
      session_id: sessionId,
      last_seen_checkpoint_id: lastCheckpointId || lastCheckpointRef.current,
    })
  }, [send])

  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return {
    state,
    connect,
    disconnect,
    send,
    submitAnswer,
    reconnect,
  }
}

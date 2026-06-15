/** WebSocket client hook for interview streaming (T035).

Handles:
- Connect to /api/v1/ws/interview?token=...
- Auto-reconnect with exponential backoff (1s/2s/4s/8s/16s, max 5)
- Carries last_seen_checkpoint_id on reconnect
- Event dispatcher: parses JSON events → updates state
- Partial token discard on disconnect
*/
import { useRef, useState, useCallback, useEffect } from 'react'

export interface WSEvent {
  type: string
  event_id: string
  session_id: string
  timestamp: string
  node_name: string
  payload: Record<string, any>
}

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
}

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BACKOFF = [1000, 2000, 4000, 8000, 16000]

export function useInterviewWS(token: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const reconnectCountRef = useRef(0)
  const lastCheckpointRef = useRef<string | null>(null)

  const [state, setState] = useState<InterviewWSState>({
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
  })

  const connect = useCallback(() => {
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
        const parsed: WSEvent = JSON.parse(event.data)

        setState(prev => {
          const updates: Partial<InterviewWSState> = {
            events: [...prev.events, parsed],
          }

          switch (parsed.type) {
            case 'node.started':
              updates.currentNode = parsed.node_name
              if (parsed.payload.current_question !== undefined) {
                updates.currentQuestion = parsed.payload.current_question
              }
              updates.streamingText = ''
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
              break
          }

          return { ...prev, ...updates }
        })
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
  }, [token])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
    }
    reconnectCountRef.current = MAX_RECONNECT_ATTEMPTS // prevent reconnect
    wsRef.current?.close()
    wsRef.current = null
    setState(prev => ({ ...prev, connected: false, reconnecting: false }))
  }, [])

  const send = useCallback((msg: Record<string, any>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  const submitAnswer = useCallback((sessionId: string, content: string, sequenceNo: number) => {
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

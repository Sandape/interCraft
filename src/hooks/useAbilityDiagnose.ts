/** useAbilityDiagnose — React hook for M18 ability diagnose WS subscription. */
import { useCallback, useEffect, useRef, useState } from 'react'

export interface AbilityDiagnoseState {
  updating: boolean
  updated: boolean
  summary: string | null
  error: string | null
}

export function useAbilityDiagnose(userId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const [state, setState] = useState<AbilityDiagnoseState>({
    updating: false,
    updated: false,
    summary: null,
    error: null,
  })

  const connect = useCallback(() => {
    if (!userId || wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = location.host
    const token = getAccessTokenFromStorage()
    if (!token) return

    const url = `${protocol}//${host}/api/v1/ws/interview?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.event === 'agent.final' && data.graph === 'ability_diagnose') {
          setState({
            updating: false,
            updated: true,
            summary: data.data?.summary || null,
            error: null,
          })
        }
      } catch {
        // Ignore non-JSON
      }
    }

    ws.onclose = () => {
      wsRef.current = null
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [userId])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect])

  const reset = useCallback(() => {
    setState({ updating: false, updated: false, summary: null, error: null })
  }, [])

  return { ...state, reset }
}

function getAccessTokenFromStorage(): string | null {
  try {
    const raw = sessionStorage.getItem('auth_tokens') || localStorage.getItem('auth_tokens')
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed.access_token || null
  } catch {
    return null
  }
}

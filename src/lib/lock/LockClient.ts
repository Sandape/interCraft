/** T037 — LockClient: WebSocket connection for lock events.

Manages a single WS connection per instance, with exponential backoff
reconnect and event dispatch.
*/
export interface LockEvent {
  type: 'lock.acquired' | 'lock.released' | 'lock.lost' | 'error'
  resource_type: string
  resource_id: string
  user_id?: string
  user_name?: string
  device_id?: string
  acquired_at?: string
  released_at?: string
  reason?: string
  message?: string
  code?: string
}

export type LockEventCallback = (event: LockEvent) => void
export type DisconnectCallback = () => void

const INITIAL_RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000

export class LockClient {
  private _ws: WebSocket | null = null
  private _getToken: () => string
  private _deviceId: string
  private _baseUrl: string
  private _eventCallbacks: LockEventCallback[] = []
  private _disconnectCallbacks: DisconnectCallback[] = []
  private _heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private _reconnectDelay = INITIAL_RECONNECT_DELAY
  private _lockId: string | null = null
  private _resourceType: string | null = null
  private _resourceId: string | null = null

  constructor(getToken: () => string, deviceId: string, baseUrl?: string) {
    this._getToken = getToken
    this._deviceId = deviceId
    this._baseUrl = baseUrl ?? 'ws://localhost:8000'
  }

  connect(): void {
    if (this._ws?.readyState === WebSocket.OPEN) return

    const token = this._getToken()
    if (!token) return

    const url = `${this._baseUrl}/api/v1/ws/locks?token=${token}&device_id=${this._deviceId}`
    this._ws = new WebSocket(url)

    this._ws.onopen = () => {
      this._reconnectDelay = INITIAL_RECONNECT_DELAY
    }

    this._ws.onmessage = (ev: MessageEvent) => {
      try {
        const event: LockEvent = JSON.parse(ev.data as string)
        this._eventCallbacks.forEach((cb) => cb(event))
      } catch {
        // ignore parse errors
      }
    }

    this._ws.onclose = () => {
      this._disconnectCallbacks.forEach((cb) => cb())
      this._scheduleReconnect()
    }

    this._ws.onerror = () => {
      // onclose will be called after this
    }
  }

  onEvent(callback: LockEventCallback): void {
    this._eventCallbacks.push(callback)
  }

  onDisconnect(callback: DisconnectCallback): void {
    this._disconnectCallbacks.push(callback)
  }

  sendHeartbeat(lockId: string, resourceType: string, resourceId: string): void {
    if (this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(
        JSON.stringify({
          type: 'lock.heartbeat',
          lock_id: lockId,
          resource_type: resourceType,
          resource_id: resourceId,
        }),
      )
    } else {
      // HTTP fallback when WebSocket is not connected
      void this._httpHeartbeat(lockId)
    }
  }

  private async _httpHeartbeat(lockId: string): Promise<void> {
    try {
      const token = this._getToken()
      await fetch(`${this._baseUrl.replace('ws', 'http')}/api/v1/locks/${lockId}/heartbeat`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch {
      // Silently ignore failed heartbeat — retry on next interval
    }
  }

  startHeartbeat(lockId: string, resourceType: string, resourceId: string): void {
    this._lockId = lockId
    this._resourceType = resourceType
    this._resourceId = resourceId
    this.stopHeartbeat()
    this._heartbeatTimer = setInterval(() => {
      this.sendHeartbeat(lockId, resourceType, resourceId)
    }, 60_000)
  }

  stopHeartbeat(): void {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer)
      this._heartbeatTimer = null
    }
  }

  disconnect(): void {
    this.stopHeartbeat()
    if (this._ws) {
      this._ws.onclose = null
      this._ws.close()
      this._ws = null
    }
  }

  private _scheduleReconnect(): void {
    setTimeout(() => {
      this.connect()
      this._reconnectDelay = Math.min(
        this._reconnectDelay * 2,
        MAX_RECONNECT_DELAY,
      )
    }, this._reconnectDelay)
  }
}

/** Singleton factory — creates a new instance per session. */
export function createLockClient(
  getToken: () => string,
  deviceId: string,
  baseUrl?: string,
): LockClient {
  return new LockClient(getToken, deviceId, baseUrl)
}

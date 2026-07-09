/** AgentRepository — Personal Agent + WeChat binding (REQ-052). */
import { request } from '../api/client'

export interface QrcodeData {
  qrcode_token: string
  /** Direct iLink / WeChat scan URL. */
  qrcode_url: string
  /** Browser-renderable PNG endpoint URL. */
  qrcode_image_url: string
  expires_at: string
  expires_in_sec: number
}

/**
 * Build the `<img src=...>` value from the server response.
 */
export function resolveQrcodeSrc(data: QrcodeData): string {
  return data.qrcode_image_url
}

export interface QrcodeStatusData {
  status: 'waiting' | 'scanned' | 'confirmed' | 'expired'
  wechat_nickname?: string | null
  wechat_avatar_url?: string | null
}

export interface BindingStatus {
  bound: boolean
  wechat_nickname?: string | null
  wechat_avatar_url?: string | null
  bound_at?: string | null
  agent_status: 'active' | 'degraded' | 'dormant'
}

export interface AgentStatus {
  user_id: string
  status: 'active' | 'degraded' | 'dormant'
  display_name: string
  wechat_bound: boolean
  last_heartbeat_at?: string | null
  messages_sent_total: number
  messages_received_total: number
}

export interface AgentPreferences {
  display_name: string
  quiet_hours_start?: string | null
  quiet_hours_end?: string | null
  notification_mode: 'realtime' | 'hourly_digest'
}

export const AgentRepository = {
  async fetchQrcode(): Promise<QrcodeData> {
    return request({ method: 'GET', path: '/api/v1/agent/wechat/qrcode' })
  },

  async pollQrcodeStatus(qrcodeToken: string): Promise<QrcodeStatusData> {
    return request({
      method: 'GET',
      path: '/api/v1/agent/wechat/qrcode/status',
      query: { qrcode_token: qrcodeToken },
    })
  },

  async fetchBindingStatus(): Promise<BindingStatus> {
    return request({ method: 'GET', path: '/api/v1/agent/wechat/binding' })
  },

  async unbindWechat(): Promise<{ message: string }> {
    return request({ method: 'DELETE', path: '/api/v1/agent/wechat/binding' })
  },

  async fetchAgentStatus(): Promise<AgentStatus> {
    return request({ method: 'GET', path: '/api/v1/agent/status' })
  },

  async fetchPreferences(): Promise<AgentPreferences> {
    return request({ method: 'GET', path: '/api/v1/agent/preferences' })
  },

  async updatePreferences(data: Partial<AgentPreferences>): Promise<AgentPreferences> {
    return request({
      method: 'PATCH',
      path: '/api/v1/agent/preferences',
      body: data,
    })
  },
}

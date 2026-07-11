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
  /** Backend / iLink contract uses ``wait`` (not ``waiting``). */
  status: 'wait' | 'scanned' | 'confirmed' | 'expired'
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

export interface AgentConsumerStatus {
  enabled: boolean
  state: 'disabled' | 'active' | 'standby'
}

export interface AgentTask {
  id: string
  kind: string
  status: string
  stage: string
  progress_percent?: number | null
  summary: string
  result_json?: Record<string, unknown> | null
  error_category?: string | null
  created_at: string
  updated_at: string
  /** REQ-061 T089 — server-derived DTO fields */
  task_id?: string | null
  canonical_status?: string | null
  available_actions?: string[]
  terminal?: boolean
  task_version?: number
  point_summary?: {
    quoted_max?: number
    reserved?: number
    settled?: number
    released?: number
    settlement_status?: string
  } | null
  runtime_links?: Record<string, string> | null
}

export interface AgentTaskList {
  items: AgentTask[]
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

  async fetchConsumerStatus(): Promise<AgentConsumerStatus> {
    return request({ method: 'GET', path: '/api/v1/agent/consumer/status' })
  },

  async fetchTasks(status?: string): Promise<AgentTaskList> {
    return request({
      method: 'GET',
      path: '/api/v1/agent/tasks',
      query: status ? { status } : undefined,
    })
  },

  async getTask(taskId: string): Promise<AgentTask> {
    return request({ method: 'GET', path: `/api/v1/agent/tasks/${taskId}` })
  },

  async cancelTask(taskId: string): Promise<{ id: string; status: string }> {
    return request({ method: 'POST', path: `/api/v1/agent/tasks/${taskId}/cancel` })
  },

  async resumeTask(taskId: string): Promise<{ id: string; status: string }> {
    return request({ method: 'POST', path: `/api/v1/agent/tasks/${taskId}/resume` })
  },
}

/**
 * Account API service — lifecycle, export, import, devices, security, subscription.
 */
import { apiClient, withMock } from './client'

export interface DeleteAccountResponse {
  status: string
  scheduled_purge_at: string | null
  cancellation_deadline: string | null
  message: string
}

export interface CancelDeletionResponse {
  status: string
  message: string
}

export interface DeletionStatusResponse {
  status: string
  is_deleting: boolean
  scheduled_purge_at: string | null
  cancellation_deadline: string | null
  can_cancel: boolean | null
  days_until_purge: number | null
  days_until_cancellation_deadline: number | null
  message: string | null
}

export interface ExportTaskResponse {
  task_id: string
  status: string
  estimated_minutes: number
}

export interface ExportStatusResponse {
  task_id: string
  status: string
  progress_pct: number
  created_at: string
  completed_at: string | null
  download_url: string | null
  expires_at: string | null
  file_size_bytes: number | null
}

export interface NotificationItem {
  id: string
  type: string
  title: string
  message: string
  related_task_id: string | null
  is_read: boolean
  created_at: string
}

export interface NotificationCenterResponse {
  notifications: NotificationItem[]
  unread_count: number
}

export interface DeviceItem {
  id: string
  device_name: string | null
  browser: string | null
  ip: string | null
  last_seen_at: string | null
  created_at: string
  is_current: boolean
}

export interface DevicesResponse {
  devices: DeviceItem[]
}

export interface SubscriptionPlan {
  plan: string
  monthly_token_quota: number
  features: Record<string, unknown>
  is_active: boolean
}

export interface CurrentSubscription {
  plan: string
  monthly_token_quota: number
  monthly_token_used: number
  monthly_token_remaining: number
  usage_pct: number
  reset_date: string
  can_start_interview: boolean
}

export interface PreCheckResponse {
  can_proceed: boolean
  estimated_token_cost: number
  monthly_token_remaining_before: number
  monthly_token_remaining_after: number
}

export interface ChangePasswordInput {
  current_password: string
  new_password: string
}

export interface LoginHistoryItem {
  id: string
  ip: string | null
  user_agent: string | null
  device_name: string | null
  created_at: string
}

export const accountApi = {
  // ---- Account Lifecycle ----
  deleteAccount: () =>
    withMock(
      () => apiClient.request<DeleteAccountResponse>('POST', '/api/v1/account/delete', { confirmation: true }),
      () => ({ status: 'soft_deleted', scheduled_purge_at: null, cancellation_deadline: null, message: '开发模式：模拟注销成功' }),
    )(),

  cancelDeletion: () =>
    withMock(
      () => apiClient.request<CancelDeletionResponse>('POST', '/api/v1/account/cancel-deletion'),
      () => ({ status: 'active', message: '开发模式：模拟取消成功' }),
    )(),

  getDeletionStatus: () =>
    withMock(
      () => apiClient.request<DeletionStatusResponse>('GET', '/api/v1/account/deletion-status'),
      () => ({ status: 'active', is_deleting: false }),
    )(),

  // ---- Export ----
  createExport: (include?: string[]) =>
    withMock(
      () => apiClient.request<ExportTaskResponse>('POST', '/api/v1/account/export', { include }),
      () => ({ task_id: 'mock-task-id', status: 'pending', estimated_minutes: 3 }),
    )(),

  getExportStatus: (taskId: string) =>
    withMock(
      () => apiClient.request<ExportStatusResponse>('GET', `/api/v1/account/export/${taskId}/status`),
      () => ({ task_id: taskId, status: 'completed', progress_pct: 100, created_at: new Date().toISOString(), completed_at: new Date().toISOString(), download_url: null, expires_at: null, file_size_bytes: 1000 }),
    )(),

  downloadExportUrl: (taskId: string) =>
    `/api/v1/account/export/${taskId}/download`,

  // ---- Devices ----
  listDevices: () =>
    withMock(
      () => apiClient.request<DevicesResponse>('GET', '/api/v1/settings/devices'),
      () => ({ devices: [] }),
    )(),

  logoutOtherDevices: () =>
    withMock(
      () => apiClient.request<{ message: string; sessions_terminated: number }>('POST', '/api/v1/settings/devices/logout-others'),
      () => ({ message: '其他设备已下线', sessions_terminated: 0 }),
    )(),

  // ---- Security ----
  changePassword: (input: ChangePasswordInput) =>
    withMock(
      () => apiClient.request<{ message: string }>('POST', '/api/v1/settings/change-password', input),
      () => ({ message: '密码已更新' }),
    )(),

  getLoginHistory: () =>
    withMock(
      () => apiClient.request<{ items: LoginHistoryItem[] }>('GET', '/api/v1/settings/login-history'),
      () => ({ items: [] }),
    )(),

  // ---- Subscription ----
  listPlans: () =>
    withMock(
      () => apiClient.request<{ plans: SubscriptionPlan[] }>('GET', '/api/v1/subscription/plans'),
      () => ({
        plans: [
          { plan: 'free', monthly_token_quota: 500000, features: {}, is_active: true },
          { plan: 'pro', monthly_token_quota: 5000000, features: { priority_support: true }, is_active: true },
          { plan: 'enterprise', monthly_token_quota: 50000000, features: { priority_support: true, custom_quota: true }, is_active: true },
        ],
      }),
    )(),

  getCurrentSubscription: () =>
    withMock(
      () => apiClient.request<CurrentSubscription>('GET', '/api/v1/subscription/current'),
      () => ({
        plan: 'free', monthly_token_quota: 500000, monthly_token_used: 12345,
        monthly_token_remaining: 487655, usage_pct: 2.5, reset_date: '2026-07-01T00:00:00Z',
        can_start_interview: true,
      }),
    )(),

  subscriptionPreCheck: () =>
    withMock(
      () => apiClient.request<PreCheckResponse>('POST', '/api/v1/subscription/pre-check'),
      () => ({ can_proceed: true, estimated_token_cost: 28000, monthly_token_remaining_before: 487655, monthly_token_remaining_after: 459655 }),
    )(),

  // ---- Notification ----
  getNotificationCenter: () =>
    withMock(
      () => apiClient.request<NotificationCenterResponse>('GET', '/api/v1/account/notification-center'),
      () => ({ notifications: [], unread_count: 0 }),
    )(),
}

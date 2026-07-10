/** API client for ability profile endpoints (Feature 006 / 024). */
import { request } from './client'
import { env } from './env'
import { getAccessToken } from './token-storage'

const BASE = '/api/v1/ability-profile'

// ─── Types ──────────────────────────────────────────────────────────────────

export interface DimensionHistoryPoint {
  date: string
  actual_score: number
  ideal_score: number
}

export interface DashboardDimension {
  key: string
  label_zh: string
  actual_score: number
  ideal_score: number
  self_assessed_score: number | null
  source: string
  trend: 'up' | 'down' | 'stable'
  history: DimensionHistoryPoint[]
}

export interface DashboardResponse {
  dimensions: DashboardDimension[]
  generated_at: string
}

export interface ShareLinkResponse {
  id: string
  token: string
  url: string
  expires_at: string | null
  created_at: string
}

export interface ShareLinkListItem {
  id: string
  token: string
  url: string
  expires_at: string | null
  revoked_at: string | null
  access_count: number
  last_accessed_at: string | null
  status: 'active' | 'expired' | 'revoked'
  created_at: string
}

export interface SharedProfileResponse {
  owner: { name: string; title: string | null }
  generated_at: string
  dimensions: { key: string; label_zh: string; actual_score: number; ideal_score?: number }[]
}

export interface ExportTriggerResponse {
  export_id: string
  status: string
  estimated_wait_seconds: number
  requested_at: string
}

export interface ExportStatusResponse {
  export_id: string
  status: string
  file_size_bytes: number | null
  download_url: string | null
  requested_at: string
  completed_at: string | null
}

export interface ExportListItem {
  export_id: string
  status: string
  file_size_bytes: number | null
  requested_at: string
  completed_at: string | null
}

export interface AdminDashboardResponse extends DashboardResponse {
  viewed_user_id: string
  viewed_user_name: string
}

// ─── API calls ──────────────────────────────────────────────────────────────

export async function fetchDashboard(): Promise<{ data: DashboardResponse }> {
  return request<{ data: DashboardResponse }>('GET', `${BASE}/dashboard`)
}

export async function createShareLink(expiresInHours?: number): Promise<{ data: ShareLinkResponse }> {
  return request<{ data: ShareLinkResponse }>('POST', `${BASE}/share`, {
    expires_in_hours: expiresInHours || undefined,
  })
}

export async function listShareLinks(): Promise<{ data: ShareLinkListItem[] }> {
  return request<{ data: ShareLinkListItem[] }>('GET', `${BASE}/share`)
}

export async function revokeShareLink(linkId: string): Promise<void> {
  return request('DELETE', `${BASE}/share/${linkId}`)
}

export async function getSharedProfile(token: string): Promise<{ data: SharedProfileResponse }> {
  return request<{ data: SharedProfileResponse }>('GET', `${BASE}/share/${token}`)
}

/** Sync PDF download (024 FR-050). Triggers browser download. */
export async function downloadExportPdf(): Promise<void> {
  const token = getAccessToken()
  const url = `${env.API_BASE_URL || ''}${BASE}/export-pdf`
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(detail || `PDF export failed (${res.status})`)
  }
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/)
  const filename = match?.[1] || `ability-profile-${new Date().toISOString().slice(0, 10)}.pdf`
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  a.click()
  URL.revokeObjectURL(objectUrl)
}

/** @deprecated Prefer downloadExportPdf (sync). Kept for legacy callers. */
export async function triggerExport(): Promise<{ data: ExportTriggerResponse }> {
  return request<{ data: ExportTriggerResponse }>('POST', `${BASE}/export`)
}

export async function getExportStatus(exportId: string): Promise<{ data: ExportStatusResponse }> {
  return request<{ data: ExportStatusResponse }>('GET', `${BASE}/exports/${exportId}`)
}

export async function listExports(limit = 10): Promise<{ data: ExportListItem[] }> {
  return request<{ data: ExportListItem[] }>('GET', `${BASE}/exports?limit=${limit}`)
}

export async function downloadExport(exportId: string): Promise<Blob> {
  const token = getAccessToken()
  const url = `${env.API_BASE_URL || ''}${BASE}/exports/${exportId}/download`
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error('Download failed')
  return res.blob()
}

export async function fetchAdminDashboard(targetUserId: string): Promise<{ data: AdminDashboardResponse }> {
  return request<{ data: AdminDashboardResponse }>('GET', `${BASE}/admin/${targetUserId}`)
}

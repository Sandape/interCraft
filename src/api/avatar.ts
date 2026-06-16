/**
 * Avatar API service — upload, fetch, remove.
 *
 * Mirrors the backend Pydantic schemas in
 * backend/app/modules/avatars/schemas.py.
 */
import { deviceFingerprint } from './device-fingerprint'
import { newRequestId } from './env'
import { getAccessToken } from './token-storage'

const AVATAR_BASE = '/api/v1/users/me/avatar'

export interface AvatarOut {
  avatar_id: string
  url: string
  content_type: string
  byte_size: number
  width: number | null
  height: number | null
  created_at: string
}

export interface AvatarRemoveResponse {
  status: string
  message: string
}

export class AvatarApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {
    'X-Request-ID': newRequestId(),
    'X-Device-Fingerprint': deviceFingerprint(),
  }
  const access = getAccessToken()
  if (access) h.Authorization = `Bearer ${access}`
  return h
}

async function readError(res: Response): Promise<AvatarApiError> {
  let code = 'AVATAR_ERROR'
  let message = `头像请求失败 (${res.status})`
  try {
    const body = (await res.json()) as { error?: string; message?: string } | null
    if (body) {
      if (typeof body.error === 'string' && body.error) code = body.error
      if (typeof body.message === 'string' && body.message) message = body.message
    }
  } catch {
    // ignore parse error
  }
  return new AvatarApiError(message, code, res.status)
}

export async function uploadAvatar(file: File): Promise<AvatarOut> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(AVATAR_BASE, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  if (!res.ok) throw await readError(res)
  return (await res.json()) as AvatarOut
}

export async function removeAvatar(): Promise<AvatarRemoveResponse> {
  const res = await fetch(AVATAR_BASE, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw await readError(res)
  return (await res.json()) as AvatarRemoveResponse
}

export async function fetchAvatarBlob(avatarUrl: string): Promise<Blob> {
  const res = await fetch(avatarUrl, {
    headers: authHeaders(),
    cache: 'no-store',
  })
  if (!res.ok) throw await readError(res)
  return res.blob()
}

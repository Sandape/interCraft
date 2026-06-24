/**
 * Resume-branch avatar API — upload, fetch, remove, inherit-from-parent.
 *
 * Mirrors backend `app/modules/resumes/api_avatar.py` (spec 027 US9).
 * The stored file lives under avatar_storage_dir; the API endpoint URL
 * returned in `avatar_url` serves the bytes via `GET /avatar`.
 */
import { deviceFingerprint } from '../../../api/device-fingerprint'
import { env, newRequestId } from '../../../api/env'
import { getAccessToken } from '../../../api/token-storage'

/** Build an absolute URL against env.API_BASE_URL so MSW (vitest) can match. */
function absoluteUrl(path: string): string {
  const base = env.API_BASE_URL || ''
  if (!base) return path
  return `${base.replace(/\/$/, '')}${path}`
}

export interface BranchAvatarUploadResponse {
  branch_id: string
  url: string
  content_type: string
  byte_size: number
}

export interface BranchAvatarOkResponse {
  ok: true
}

export class BranchAvatarApiError extends Error {
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

async function readError(res: Response): Promise<BranchAvatarApiError> {
  let code = 'AVATAR_ERROR'
  let message = `头像请求失败 (${res.status})`
  try {
    const body = (await res.json()) as { error?: { code?: string; message?: string }; message?: string } | null
    if (body) {
      if (body.error) {
        if (typeof body.error.code === 'string' && body.error.code) code = body.error.code
        if (typeof body.error.message === 'string' && body.error.message) message = body.error.message
      } else {
        if (typeof body.message === 'string' && body.message) message = body.message
      }
    }
  } catch {
    // ignore parse error
  }
  return new BranchAvatarApiError(message, code, res.status)
}

export async function uploadBranchAvatar(
  branchId: string,
  file: File,
): Promise<BranchAvatarUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(absoluteUrl(`/api/v1/resume-branches/${branchId}/avatar`), {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  })
  if (!res.ok) throw await readError(res)
  return (await res.json()) as BranchAvatarUploadResponse
}

export async function deleteBranchAvatar(branchId: string): Promise<BranchAvatarOkResponse> {
  const res = await fetch(absoluteUrl(`/api/v1/resume-branches/${branchId}/avatar`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw await readError(res)
  return (await res.json()) as BranchAvatarOkResponse
}

export async function inheritBranchAvatar(branchId: string): Promise<BranchAvatarOkResponse> {
  const res = await fetch(absoluteUrl(`/api/v1/resume-branches/${branchId}/avatar/inherit`), {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw await readError(res)
  return (await res.json()) as BranchAvatarOkResponse
}

/**
 * Fetch the avatar bytes for a branch. Returns null when the branch has
 * no avatar (404). Throws on any other error.
 */
export async function fetchBranchAvatarBlob(branchId: string): Promise<Blob | null> {
  const res = await fetch(absoluteUrl(`/api/v1/resume-branches/${branchId}/avatar`), {
    headers: authHeaders(),
    cache: 'no-store',
  })
  if (res.status === 404) return null
  if (!res.ok) throw await readError(res)
  return res.blob()
}
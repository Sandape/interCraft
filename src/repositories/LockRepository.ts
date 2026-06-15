/** T039 — HTTP Lock repository interface + implementation.

Used by React Query hooks and components for lock operations.
*/
import { apiClient } from '../api/client'
import type { RequestOptions } from '../api/client'
import { ApiError, NetworkError } from '../api/errors'

export interface AcquireInput {
  resource_type: string
  resource_id: string
}

export interface LockStatus {
  locked: boolean
  lock_id?: string
  resource_type?: string
  resource_id?: string
  user_id?: string
  user_name?: string
  device_id?: string
  acquired_at?: string
  expires_at?: string
}

export interface ReleaseResponse {
  lock_id: string
  resource_type: string
  resource_id: string
  released_at: string
}

async function request<T>(
  opts: Omit<RequestOptions, 'path'> & { path: string },
): Promise<T> {
  try {
    return await apiClient.request<T>(opts)
  } catch (e) {
    if (e instanceof ApiError && !(e instanceof NetworkError)) {
      throw e
    }
    if (import.meta.env.VITE_USE_MOCK === 'true') {
      return mockRequest<T>(opts)
    }
    throw e
  }
}

function mockRequest<T>(
  opts: Omit<RequestOptions, 'path'> & { path: string },
): T {
  if (opts.method === 'POST' && opts.path.includes('/acquire')) {
    return {
      locked: true,
      lock_id: 'mock-lock-id',
      resource_type: 'resume_branch',
      resource_id: 'mock-resource-id',
      user_id: 'mock-user',
      user_name: 'Mock User',
      device_id: 'mock-device',
      acquired_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 300_000).toISOString(),
    } as unknown as T
  }
  if (opts.method === 'DELETE') {
    return {
      lock_id: 'mock-lock-id',
      resource_type: 'resume_branch',
      resource_id: 'mock-resource-id',
      released_at: new Date().toISOString(),
    } as unknown as T
  }
  if (opts.method === 'GET') {
    return {
      locked: false,
      resource_type: 'resume_branch',
      resource_id: 'mock-resource-id',
    } as unknown as T
  }
  throw new Error(`Unsupported mock: ${opts.method} ${opts.path}`)
}

export const LockRepository = {
  async acquire(input: AcquireInput): Promise<LockStatus> {
    return request<LockStatus>({
      method: 'POST',
      path: '/api/v1/locks/acquire',
      body: input,
    })
  },

  async release(lockId: string): Promise<ReleaseResponse> {
    return request<ReleaseResponse>({
      method: 'DELETE',
      path: `/api/v1/locks/${lockId}`,
    })
  },

  async getStatus(
    resourceType: string,
    resourceId: string,
  ): Promise<LockStatus> {
    return request<LockStatus>({
      method: 'GET',
      path: `/api/v1/locks/${resourceType}/${resourceId}`,
    })
  },
}

export function getLockRepository() {
  return LockRepository
}

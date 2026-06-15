import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../../api/errors'
import { useLock } from '../useLock'

const mocks = vi.hoisted(() => {
  let eventHandler: ((event: unknown) => void) | undefined

  const client = {
    onEvent: vi.fn((handler: (event: unknown) => void) => {
      eventHandler = handler
    }),
    connect: vi.fn(),
    startHeartbeat: vi.fn(),
    stopHeartbeat: vi.fn(),
    disconnect: vi.fn(),
  }

  return {
    acquire: vi.fn(),
    release: vi.fn(),
    createLockClient: vi.fn(() => client),
    client,
    emit(event: unknown) {
      eventHandler?.(event)
    },
    resetEventHandler() {
      eventHandler = undefined
    },
  }
})

vi.mock('../../../repositories/LockRepository', () => ({
  LockRepository: {
    acquire: mocks.acquire,
    release: mocks.release,
  },
}))

vi.mock('../LockClient', () => ({
  createLockClient: mocks.createLockClient,
}))

describe('useLock', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.resetEventHandler()
    sessionStorage.clear()
    sessionStorage.setItem('ic.access_token', 'test-access-token')
    sessionStorage.setItem('ic.device_fingerprint', 'test-device')
    mocks.acquire.mockResolvedValue({
      locked: true,
      lock_id: 'lock-1',
      resource_type: 'resume_branch',
      resource_id: 'resource-1',
    })
    mocks.release.mockResolvedValue({
      lock_id: 'lock-1',
      resource_type: 'resume_branch',
      resource_id: 'resource-1',
      released_at: new Date().toISOString(),
    })
  })

  afterEach(() => {
    sessionStorage.clear()
  })

  it('acquires a lock and starts heartbeat for the resource', async () => {
    const { result, unmount } = renderHook(() => useLock('resume_branch', 'resource-1'))

    await waitFor(() => expect(result.current.status).toBe('locked'))

    expect(mocks.acquire).toHaveBeenCalledWith({
      resource_type: 'resume_branch',
      resource_id: 'resource-1',
    })
    expect(mocks.client.startHeartbeat).toHaveBeenCalledWith(
      'lock-1',
      'resume_branch',
      'resource-1',
    )

    unmount()
  })

  it('keeps editing when a lock.lost event belongs to another resource', async () => {
    const { result, unmount } = renderHook(() => useLock('resume_branch', 'resource-1'))

    await waitFor(() => expect(result.current.status).toBe('locked'))

    act(() => {
      mocks.emit({
        type: 'lock.lost',
        resource_type: 'resume_branch',
        resource_id: 'resource-2',
        reason: 'heartbeat_timeout',
      })
    })

    expect(result.current.status).toBe('locked')

    unmount()
  })

  it('switches to readonly when the current resource lock is lost', async () => {
    const { result, unmount } = renderHook(() => useLock('resume_branch', 'resource-1'))

    await waitFor(() => expect(result.current.status).toBe('locked'))

    act(() => {
      mocks.emit({
        type: 'lock.lost',
        resource_type: 'resume_branch',
        resource_id: 'resource-1',
        user_id: 'user-2',
        user_name: 'Other User',
        reason: 'heartbeat_timeout',
      })
    })

    expect(result.current.status).toBe('readonly')
    expect(result.current.holder).toEqual({ userId: 'user-2', userName: 'Other User' })

    unmount()
  })

  it('treats an existing lock held by this user as editable', async () => {
    mocks.acquire.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'lock.already_held_by_you',
        message: 'Already held',
        requestId: 'req-1',
        details: { lock_id: 'existing-lock' },
      }),
    )

    const { result, unmount } = renderHook(() => useLock('resume_branch', 'resource-1'))

    await waitFor(() => expect(result.current.status).toBe('locked'))
    expect(mocks.client.startHeartbeat).toHaveBeenCalledWith(
      'existing-lock',
      'resume_branch',
      'resource-1',
    )

    unmount()
  })

  it('becomes readonly when another user holds the resource lock', async () => {
    mocks.acquire.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'lock.resource_locked',
        message: 'Locked by someone else',
        requestId: 'req-1',
        details: {
          locked_by: {
            user_id: 'user-2',
            user_name: 'Other User',
          },
        },
      }),
    )

    const { result } = renderHook(() => useLock('resume_branch', 'resource-1'))

    await waitFor(() => expect(result.current.status).toBe('readonly'))
    expect(result.current.holder).toEqual({ userId: 'user-2', userName: 'Other User' })
  })
})

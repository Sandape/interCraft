/** T038 — useLock React hook.

Manages pessimistic lock lifecycle: acquire → heartbeat → release.

Usage:
  const { status, holder, acquire, release, error } = useLock('resume_branch', branchId)
*/
import { useState, useEffect, useCallback, useRef } from 'react'
import { LockRepository } from '../../repositories/LockRepository'
import { createLockClient, type LockClient, type LockEvent } from './LockClient'
import { ApiError } from '../../api/errors'

export type LockStatusState =
  | 'idle'
  | 'acquiring'
  | 'locked'
  | 'readonly'
  | 'conflict'

export interface LockHolder {
  userId: string
  userName: string
}

export interface UseLockReturn {
  status: LockStatusState
  holder: LockHolder | undefined
  acquire: () => Promise<void>
  release: () => Promise<void>
  error: string | null
}

export function useLock(
  resourceType: string,
  resourceId: string | null,
): UseLockReturn {
  const [status, setStatus] = useState<LockStatusState>('idle')
  const [holder, setHolder] = useState<LockHolder | undefined>()
  const [error, setError] = useState<string | null>(null)
  const clientRef = useRef<LockClient | null>(null)
  const lockIdRef = useRef<string | null>(null)

  const getToken = useCallback(() => {
    if (typeof sessionStorage === 'undefined') return ''
    return sessionStorage.getItem('ic.access_token') ?? ''
  }, [])

  const getDeviceId = useCallback(() => {
    if (typeof sessionStorage === 'undefined') return 'unknown'
    return sessionStorage.getItem('ic.device_fingerprint') ?? 'unknown'
  }, [])

  const startHeartbeat = useCallback(
    (lockId: string) => {
      const deviceId = getDeviceId()
      const client = createLockClient(getToken, deviceId)
      clientRef.current = client
      client.onEvent((event: LockEvent) => {
        if (event.resource_type !== resourceType || event.resource_id !== resourceId) {
          return
        }
        if (event.type === 'lock.lost') {
          setStatus('readonly')
          setHolder(
            event.user_id
              ? {
                  userId: event.user_id,
                  userName: event.user_name ?? '',
                }
              : undefined,
          )
        }
      })
      client.connect()
      if (resourceId) {
        client.startHeartbeat(lockId, resourceType, resourceId)
      }
    },
    [resourceType, resourceId, getToken, getDeviceId],
  )

  const acquire = useCallback(async () => {
    if (!resourceId) return
    setStatus('acquiring')
    setError(null)
    try {
      const result = await LockRepository.acquire({
        resource_type: resourceType,
        resource_id: resourceId,
      })
      const lockId = result.lock_id
      if (lockId) {
        lockIdRef.current = lockId
        startHeartbeat(lockId)
      }
      setStatus('locked')
    } catch (e: unknown) {
      let errorCode: string | undefined
      let details: Record<string, unknown> | undefined

      if (e instanceof ApiError) {
        errorCode = e.code
        details = e.details as Record<string, unknown> | undefined
      }

      if (errorCode === 'lock.already_held_by_you') {
        const existingLockId = details?.lock_id as string | undefined
        if (existingLockId) {
          lockIdRef.current = existingLockId
          startHeartbeat(existingLockId)
        }
        setStatus('locked')
      } else if (errorCode === 'lock.resource_locked') {
        setStatus('readonly')
        const lockedBy = details?.locked_by as
          | { user_id?: string; user_name?: string }
          | undefined
        if (lockedBy) {
          setHolder({
            userId: lockedBy.user_id ?? '',
            userName: lockedBy.user_name ?? '',
          })
        }
      } else {
        setStatus('conflict')
        setError((e instanceof Error ? e.message : '') || 'Failed to acquire lock')
      }
    }
  }, [resourceType, resourceId, startHeartbeat])

  const release = useCallback(async () => {
    if (!lockIdRef.current) return
    try {
      await LockRepository.release(lockIdRef.current)
    } catch {
      // Lock may already be expired
    }
    if (clientRef.current) {
      clientRef.current.stopHeartbeat()
      clientRef.current.disconnect()
    }
    lockIdRef.current = null
    setStatus('idle')
    setHolder(undefined)
  }, [])

  // Cleanup on unmount — release lock and disconnect WS
  useEffect(() => {
    return () => {
      if (lockIdRef.current) {
        LockRepository.release(lockIdRef.current).catch(() => {})
        lockIdRef.current = null
      }
      if (clientRef.current) {
        clientRef.current.disconnect()
      }
    }
  }, [])

  // Auto-acquire if resourceId provided
  useEffect(() => {
    if (resourceId && status === 'idle') {
      acquire()
    }
  }, [resourceId, status, acquire])

  return {
    status,
    holder,
    acquire,
    release,
    error,
  }
}

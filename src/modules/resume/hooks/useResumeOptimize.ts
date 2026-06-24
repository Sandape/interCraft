/**
 * useResumeOptimize — US5 state machine for AI resume optimization.
 *
 * State machine:
 *   idle → polling → waiting_patches → applying → done
 *                          ↓                ↓
 *                       error/timeout    error
 *
 * Polling: exponential backoff 1s → 2s → 4s → 8s → 16s (capped at 30s),
 * stops when status becomes 'waiting_interrupt' or 60s budget elapses.
 *
 * Per-patch: each patch gets a stable 0-based index. User can toggle accept
 * (default = all accepted). On apply, accepted indices are sent to backend.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { resumeOptimizeRepo, type StartInput, type StateResponse, type ConfirmResponse } from '../repositories/resumeOptimizeRepo'

export type ResumeOptimizeStatus =
  | 'idle'
  | 'polling'
  | 'waiting_patches'
  | 'applying'
  | 'done'
  | 'error'
  | 'timeout'

/** Shape of a single proposed patch, derived from the backend JSON Patch list. */
export interface ProposedPatch {
  index: number
  op: string
  path: string
  value: unknown
  /** Snapshot of the original value at path (for diff display). */
  oldValue: unknown
}

export interface ResumeOptimizeState {
  status: ResumeOptimizeStatus
  loading: boolean
  error: string | null
  threadId: string | null
  summary: string | null
  /** Patches returned by the AI. Stable index assigned here, used as React key. */
  patches: ProposedPatch[]
  /** Subset of patch indices the user has accepted. Default = all accepted. */
  acceptedIndices: Set<number>
  versionId: string | null
  /** Seconds since polling started (for elapsed-time display). */
  elapsedSec: number
}

const POLL_BACKOFF_MS = [1000, 2000, 4000, 8000, 16000, 30000]
const POLL_TIMEOUT_MS = 60_000
const APPLY_PATCH_WAITING = 'waiting_interrupt'

function initialState(): ResumeOptimizeState {
  return {
    status: 'idle',
    loading: false,
    error: null,
    threadId: null,
    summary: null,
    patches: [],
    acceptedIndices: new Set(),
    versionId: null,
    elapsedSec: 0,
  }
}

/** Look up the value at a JSON-Pointer-ish path like `/blocks/2/content_md`. */
function readAtPath(blocks: unknown, path: string): unknown {
  if (!path || !path.startsWith('/')) return undefined
  const parts = path.split('/').slice(1)
  let cur: unknown = blocks
  for (const part of parts) {
    if (cur == null) return undefined
    if (Array.isArray(cur)) {
      const idx = Number(part)
      if (Number.isNaN(idx)) return undefined
      cur = cur[idx]
    } else if (typeof cur === 'object') {
      cur = (cur as Record<string, unknown>)[part]
    } else {
      return undefined
    }
  }
  return cur
}

/** Hydrate raw backend patches with stable indices and a snapshot of old value. */
function hydratePatches(
  rawPatches: Array<Record<string, unknown>> | null,
  currentBlocks: unknown,
): { patches: ProposedPatch[]; acceptedIndices: Set<number> } {
  if (!rawPatches || rawPatches.length === 0) {
    return { patches: [], acceptedIndices: new Set() }
  }
  const patches: ProposedPatch[] = rawPatches.map((p, i) => {
    const path = String(p.path ?? '')
    let oldValue: unknown = undefined
    // Best-effort lookup: walk up the path until we find an array of blocks.
    if (path.startsWith('/blocks/')) {
      oldValue = readAtPath(currentBlocks, path)
    }
    return {
      index: i,
      op: String(p.op ?? 'replace'),
      path,
      value: p.value,
      oldValue,
    }
  })
  return { patches, acceptedIndices: new Set(patches.map((p) => p.index)) }
}

export interface UseResumeOptimizeReturn extends ResumeOptimizeState {
  start: (input: StartInput) => Promise<void>
  cancel: () => void
  togglePatch: (index: number) => void
  acceptAll: () => void
  rejectAll: () => void
  apply: () => Promise<ConfirmResponse | null>
  discard: () => Promise<ConfirmResponse | null>
  reset: () => void
}

export function useResumeOptimize(): UseResumeOptimizeReturn {
  const [state, setState] = useState<ResumeOptimizeState>(initialState)

  // Refs for cancellation and bookkeeping that should not trigger re-renders.
  const cancelRef = useRef<{ cancelled: boolean }>({ cancelled: false })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const budgetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startedAtRef = useRef<number>(0)

  const clearTimers = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    if (budgetTimerRef.current) {
      clearTimeout(budgetTimerRef.current)
      budgetTimerRef.current = null
    }
    if (tickRef.current) {
      clearInterval(tickRef.current)
      tickRef.current = null
    }
  }, [])

  const pollOnce = useCallback(
    async (threadId: string, attempt: number) => {
      const token = cancelRef.current
      if (token.cancelled) return

      try {
        const stateRes: StateResponse = await resumeOptimizeRepo.getState(threadId)

        if (token.cancelled) return

        const isReady = stateRes.status === APPLY_PATCH_WAITING || stateRes.proposed_patches
        if (isReady) {
          // Use the snapshot returned by getState if present; fall back to [].
          const { patches, acceptedIndices } = hydratePatches(
            (stateRes.proposed_patches as Array<Record<string, unknown>> | null) ?? null,
            null,
          )
          clearTimers()
          setState((prev) => ({
            ...prev,
            status: 'waiting_patches',
            loading: false,
            summary: stateRes.summary ?? null,
            patches,
            acceptedIndices,
          }))
          return
        }

        // Not ready — schedule next attempt with exponential backoff.
        const delay = POLL_BACKOFF_MS[Math.min(attempt, POLL_BACKOFF_MS.length - 1)]
        timerRef.current = setTimeout(() => {
          if (token.cancelled) return
          void pollOnce(threadId, attempt + 1)
        }, delay)
      } catch (err) {
        if (token.cancelled) return
        // Transient error — keep polling until timeout.
        const delay = POLL_BACKOFF_MS[Math.min(attempt, POLL_BACKOFF_MS.length - 1)]
        timerRef.current = setTimeout(() => {
          if (token.cancelled) return
          void pollOnce(threadId, attempt + 1)
        }, delay)
      }
    },
    [clearTimers],
  )

  const start = useCallback(
    async (input: StartInput) => {
      // Reset cancellation + state.
      cancelRef.current = { cancelled: false }
      clearTimers()
      startedAtRef.current = Date.now()
      setState({ ...initialState(), status: 'polling', loading: true })

      // Tick elapsed time every second.
      tickRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startedAtRef.current) / 1000)
        setState((prev) => (prev.elapsedSec === elapsed ? prev : { ...prev, elapsedSec: elapsed }))
      }, 1000)

      // Enforce 60s budget.
      budgetTimerRef.current = setTimeout(() => {
        if (cancelRef.current.cancelled) return
        cancelRef.current.cancelled = true
        clearTimers()
        setState((prev) => ({
          ...prev,
          status: 'timeout',
          loading: false,
          error: '优化超时,请稍后重试 (60s)',
        }))
      }, POLL_TIMEOUT_MS)

      try {
        const res = await resumeOptimizeRepo.start(input)
        if (cancelRef.current.cancelled) return
        setState((prev) => ({ ...prev, threadId: res.thread_id, status: 'polling' }))
        void pollOnce(res.thread_id, 0)
      } catch (err) {
        if (cancelRef.current.cancelled) return
        clearTimers()
        setState((prev) => ({
          ...prev,
          status: 'error',
          loading: false,
          error: err instanceof Error ? err.message : '启动优化失败',
        }))
      }
    },
    [clearTimers, pollOnce],
  )

  const cancel = useCallback(() => {
    cancelRef.current.cancelled = true
    clearTimers()
    setState((prev) => ({ ...initialState() }))
  }, [clearTimers])

  const togglePatch = useCallback((index: number) => {
    setState((prev) => {
      const next = new Set(prev.acceptedIndices)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return { ...prev, acceptedIndices: next }
    })
  }, [])

  const acceptAll = useCallback(() => {
    setState((prev) => ({
      ...prev,
      acceptedIndices: new Set(prev.patches.map((p) => p.index)),
    }))
  }, [])

  const rejectAll = useCallback(() => {
    setState((prev) => ({ ...prev, acceptedIndices: new Set() }))
  }, [])

  const apply = useCallback(async (): Promise<ConfirmResponse | null> => {
    const { threadId, patches, acceptedIndices } = state
    if (!threadId) return null
    if (patches.length === 0) return null
    setState((prev) => ({ ...prev, status: 'applying', loading: true, error: null }))
    try {
      const allAccepted = acceptedIndices.size === patches.length
      const indices = allAccepted ? null : Array.from(acceptedIndices).sort((a, b) => a - b)
      const res = await resumeOptimizeRepo.confirm(threadId, 'apply', indices)
      setState((prev) => ({
        ...prev,
        status: 'done',
        loading: false,
        versionId: res.version_id,
      }))
      return res
    } catch (err) {
      setState((prev) => ({
        ...prev,
        status: 'error',
        loading: false,
        error: err instanceof Error ? err.message : '应用修改失败',
      }))
      return null
    }
  }, [state])

  const discard = useCallback(async (): Promise<ConfirmResponse | null> => {
    const { threadId } = state
    if (!threadId) return null
    setState((prev) => ({ ...prev, status: 'applying', loading: true, error: null }))
    try {
      const res = await resumeOptimizeRepo.confirm(threadId, 'discard', null)
      setState((prev) => ({ ...prev, status: 'done', loading: false }))
      return res
    } catch (err) {
      setState((prev) => ({
        ...prev,
        status: 'error',
        loading: false,
        error: err instanceof Error ? err.message : '放弃失败',
      }))
      return null
    }
  }, [state])

  const reset = useCallback(() => {
    cancelRef.current.cancelled = true
    clearTimers()
    setState(initialState())
  }, [clearTimers])

  // Clean up timers on unmount.
  useEffect(() => {
    return () => clearTimers()
  }, [clearTimers])

  return { ...state, start, cancel, togglePatch, acceptAll, rejectAll, apply, discard, reset }
}

export const __testables__ = {
  readAtPath,
  hydratePatches,
  POLL_BACKOFF_MS,
  POLL_TIMEOUT_MS,
}

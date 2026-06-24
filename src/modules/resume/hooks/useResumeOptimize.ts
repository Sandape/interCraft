/** useResumeOptimize — React hook for M16 Resume Optimize flow. */
import { useCallback, useState } from 'react'
import { resumeOptimizeRepo, type StartInput, type StateResponse, type ConfirmResponse } from '../repositories/resumeOptimizeRepo'

export interface ResumeOptimizeState {
  loading: boolean
  error: string | null
  threadId: string | null
  status: string | null
  proposedPatches: Array<Record<string, unknown>> | null
  summary: string | null
  versionId: string | null
}

export function useResumeOptimize() {
  const [state, setState] = useState<ResumeOptimizeState>({
    loading: false,
    error: null,
    threadId: null,
    status: null,
    proposedPatches: null,
    summary: null,
    versionId: null,
  })

  const start = useCallback(async (input: StartInput) => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    try {
      const res = await resumeOptimizeRepo.start(input)
      setState(prev => ({
        ...prev,
        loading: false,
        threadId: res.thread_id,
        status: res.status,
      }))
      // Poll for state to get patches
      await pollState(res.thread_id)
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to start optimization',
      }))
    }
  }, [])

  const pollState = useCallback(async (threadId: string) => {
    try {
      const stateRes = await resumeOptimizeRepo.getState(threadId)
      setState(prev => ({
        ...prev,
        status: stateRes.status,
        proposedPatches: stateRes.proposed_patches,
        summary: stateRes.summary,
      }))
    } catch {
      // Poll failed, will retry later
    }
  }, [])

  const confirm = useCallback(async (decision: 'apply' | 'discard'): Promise<ConfirmResponse | null> => {
    const { threadId } = state
    if (!threadId) return null
    setState(prev => ({ ...prev, loading: true }))
    try {
      const res = await resumeOptimizeRepo.confirm(threadId, decision)
      setState(prev => ({
        ...prev,
        loading: false,
        status: res.status,
        versionId: res.version_id,
      }))
      return res
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to confirm',
      }))
      return null
    }
  }, [state.threadId])

  const reset = useCallback(() => {
    setState({
      loading: false,
      error: null,
      threadId: null,
      status: null,
      proposedPatches: null,
      summary: null,
      versionId: null,
    })
  }, [])

  return { ...state, start, confirm, reset }
}

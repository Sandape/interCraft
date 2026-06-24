/**
 * Resume version mutations.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { getResumeVersionRepository } from '../../repositories/types'
import type { CreateVersionInput, ResumeVersionSummary, RollbackResponse } from '@/modules/resume/api/types'
import { VERSIONS_KEY } from '../queries/useResumeVersions'

export function useSaveVersion(branchId: string) {
  const qc = useQueryClient()
  return useMutation<ResumeVersionSummary, Error, CreateVersionInput>({
    mutationFn: (input) => getResumeVersionRepository().save(branchId, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: VERSIONS_KEY(branchId) }),
  })
}

export function useRollbackVersion(branchId: string) {
  const qc = useQueryClient()
  return useMutation<RollbackResponse, Error, { versionNo: number; newName?: string }>({
    mutationFn: ({ versionNo, newName }) =>
      getResumeVersionRepository().rollback(branchId, versionNo, newName),
    onSuccess: () => qc.invalidateQueries({ queryKey: VERSIONS_KEY(branchId) }),
  })
}

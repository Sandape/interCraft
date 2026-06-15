/**
 * Resume version queries.
 */
import { useQuery } from '@tanstack/react-query'
import { getResumeVersionRepository } from '../../repositories/types'
import type { ResumeVersionDetail, ResumeVersionSummary } from '../../api/types'

export const VERSIONS_KEY = (branchId: string) => ['versions', branchId] as const
export const VERSION_KEY = (branchId: string, no: number) => ['versions', branchId, no] as const

export function useResumeVersions(branchId: string | null) {
  return useQuery<ResumeVersionSummary[]>({
    queryKey: branchId ? VERSIONS_KEY(branchId) : ['versions', 'null'],
    queryFn: () => getResumeVersionRepository().list(branchId!),
    enabled: !!branchId,
  })
}

export function useResumeVersion(branchId: string | null, versionNo: number | null) {
  return useQuery<ResumeVersionDetail>({
    queryKey:
      branchId && versionNo !== null
        ? VERSION_KEY(branchId, versionNo)
        : ['versions', 'null', 'null'],
    queryFn: () => getResumeVersionRepository().get(branchId!, versionNo!),
    enabled: !!branchId && versionNo !== null,
  })
}

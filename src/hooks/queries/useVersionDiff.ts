/**
 * useVersionDiff — TanStack Query hook for comparing two versions.
 *
 * Calls GET /resume-branches/:branchId/versions/:v1/diff/:v2 (US7 FR-049).
 */
import { useQuery } from '@tanstack/react-query'
import { getResumeVersionRepository } from '../../repositories/types'
import type { VersionDiff } from '@/modules/resume/api/types'

export const DIFF_KEY = (branchId: string, v1: number | null, v2: number | null) =>
  ['versions', 'diff', branchId, v1, v2] as const

export function useVersionDiff(
  branchId: string | null,
  v1No: number | null,
  v2No: number | null,
) {
  return useQuery<VersionDiff | null>({
    queryKey: DIFF_KEY(branchId ?? '', v1No, v2No),
    queryFn: async () => {
      if (!branchId || v1No === null || v2No === null) return null
      const repo = getResumeVersionRepository()
      try {
        return await repo.diff(branchId, v1No, v2No)
      } catch {
        return null
      }
    },
    enabled: !!branchId && v1No !== null && v2No !== null,
    staleTime: 60_000, // cache for 1 min — diffs are immutable
  })
}
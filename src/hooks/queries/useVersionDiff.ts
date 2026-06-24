/**
 * useVersionDiff — TanStack Query hook for comparing two versions.
 *
 * Calls GET /resume-branches/:branchId/versions/:v1/diff/:v2 (US7 FR-049).
 * Maps API snake_case response to the camelCase VersionDiff type used by
 * VersionDiffView.
 */
import { useQuery } from '@tanstack/react-query'
import { getResumeVersionRepository } from '../../repositories/types'
import type { VersionDiff, BlockDiff, BlockLineDiff } from '@/modules/resume/version-diff/block-diff'
import type { VersionDiff as ApiVersionDiff } from '@/modules/resume/api/types'

export const DIFF_KEY = (branchId: string, v1: number | null, v2: number | null) =>
  ['versions', 'diff', branchId, v1, v2] as const

function mapBlock(api: import('@/modules/resume/api/types').BlockDiff): BlockDiff {
  return {
    op: api.op,
    key: api.key,
    type: api.type,
    title: api.title,
    oldBlock: api.old_block,
    newBlock: api.new_block,
    lineDiff: api.line_diff as BlockLineDiff[] | null,
  }
}

function mapToCamelCase(api: ApiVersionDiff): VersionDiff {
  return {
    branchId: api.branch_id,
    oldVersionNo: api.old_version_no,
    newVersionNo: api.new_version_no,
    branchDiff: api.branch_diff,
    blocks: api.blocks.map(mapBlock),
    summary: api.summary,
  }
}

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
        const raw = await repo.diff(branchId, v1No, v2No)
        return mapToCamelCase(raw)
      } catch {
        return null
      }
    },
    enabled: !!branchId && v1No !== null && v2No !== null,
    staleTime: 60_000,
  })
}

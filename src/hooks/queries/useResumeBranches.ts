/**
 * Resume branch + block queries.
 */
import { useQuery } from '@tanstack/react-query'
import { getResumeRepository } from '../../repositories/types'
import { getResumeBlockRepository } from '../../repositories/types'
import type { ListBranchesQuery } from '../../repositories/ResumeRepository'
import type { BlockType, ResumeBlock, ResumeBranch } from '@/modules/resume/api/types'

export const BRANCHES_KEY = ['resumes', 'branches'] as const
export const BRANCH_KEY = (id: string) => ['resumes', 'branches', id] as const
export const BLOCKS_KEY = (branchId: string) => ['resumes', 'branches', branchId, 'blocks'] as const

export function useResumeBranches(query?: ListBranchesQuery) {
  // 027 US6 T085: re-fetch when search/filter/sort params change.
  const effective: ListBranchesQuery | undefined =
    query && (query.search || query.status_filter || query.sort)
      ? {
          search: query.search || undefined,
          status_filter: query.status_filter || undefined,
          sort: query.sort,
        }
      : undefined
  return useQuery<ResumeBranch[]>({
    queryKey: effective ? [...BRANCHES_KEY, effective] : BRANCHES_KEY,
    queryFn: () => getResumeRepository().list(effective),
    staleTime: 30_000,
  })
}

export function useResumeBranch(branchId: string | null) {
  return useQuery<ResumeBranch>({
    queryKey: branchId ? BRANCH_KEY(branchId) : ['resumes', 'branches', 'null'],
    queryFn: () => getResumeRepository().get(branchId!),
    enabled: !!branchId,
  })
}

export function useResumeBlocks(branchId: string | null, type?: BlockType) {
  return useQuery<ResumeBlock[]>({
    queryKey: branchId ? [...BLOCKS_KEY(branchId), type] : ['resumes', 'blocks', 'null'],
    queryFn: () => getResumeBlockRepository().list(branchId!, type),
    enabled: !!branchId,
  })
}

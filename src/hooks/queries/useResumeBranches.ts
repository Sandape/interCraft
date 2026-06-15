/**
 * Resume branch + block queries.
 */
import { useQuery } from '@tanstack/react-query'
import { getResumeRepository } from '../../repositories/types'
import { getResumeBlockRepository } from '../../repositories/types'
import type { BlockType, ResumeBlock, ResumeBranch } from '../../api/types'

export const BRANCHES_KEY = ['resumes', 'branches'] as const
export const BRANCH_KEY = (id: string) => ['resumes', 'branches', id] as const
export const BLOCKS_KEY = (branchId: string) => ['resumes', 'branches', branchId, 'blocks'] as const

export function useResumeBranches() {
  return useQuery<ResumeBranch[]>({
    queryKey: BRANCHES_KEY,
    queryFn: () => getResumeRepository().list(),
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

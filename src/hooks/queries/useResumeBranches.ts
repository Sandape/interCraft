/**
 * Resume branch + block queries.
 *
 * 036 Phase A.2 — v1 resume_branches tables have been retired; the
 * hook signatures are preserved as no-ops so cross-module call sites
 * (Dashboard / InterviewLive / JobsDetailPanel / Sidebar / Suggestions)
 * keep compiling while the v2 list becomes the only data source.
 */
import { useQuery } from '@tanstack/react-query'
import type { BlockType, ResumeBlock, ResumeBranch } from '@/modules/resume/api/types'

export const BRANCHES_KEY = ['resumes', 'branches'] as const
export const BRANCH_KEY = (id: string) => ['resumes', 'branches', id] as const
export const BLOCKS_KEY = (branchId: string) => ['resumes', 'branches', branchId, 'blocks'] as const

export function useResumeBranches(_query?: unknown) {
  return useQuery<ResumeBranch[]>({
    queryKey: BRANCHES_KEY,
    queryFn: () => Promise.resolve([] as ResumeBranch[]),
    staleTime: Infinity,
  })
}

export function useResumeBranch(_branchId: string | null) {
  return useQuery<ResumeBranch>({
    queryKey: ['resumes', 'branches', 'null'],
    queryFn: () => Promise.reject(new Error('v1 resume branches retired (036 Phase A.2)')),
    enabled: false,
  })
}

export function useResumeBlocks(_branchId: string | null, _type?: BlockType) {
  return useQuery<ResumeBlock[]>({
    queryKey: ['resumes', 'blocks', 'null'],
    queryFn: () => Promise.resolve([] as ResumeBlock[]),
    enabled: false,
  })
}
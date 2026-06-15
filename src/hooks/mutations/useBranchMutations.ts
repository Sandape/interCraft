/**
 * Resume branch + block mutations.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { getResumeRepository, getResumeBlockRepository } from '../../repositories/types'
import type {
  CreateBlockInput,
  CreateBranchInput,
  PatchBlockInput,
  PatchBranchInput,
  ReorderBlocksInput,
  ResumeBlock,
  ResumeBranch,
} from '../../api/types'
import { BLOCKS_KEY, BRANCHES_KEY, BRANCH_KEY } from '../queries/useResumeBranches'

export function useCreateBranch() {
  const qc = useQueryClient()
  return useMutation<ResumeBranch, Error, CreateBranchInput>({
    mutationFn: (input) => getResumeRepository().create(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: BRANCHES_KEY }),
  })
}

export function usePatchBranch() {
  const qc = useQueryClient()
  return useMutation<ResumeBranch, Error, { id: string; input: PatchBranchInput }>({
    mutationFn: ({ id, input }) => getResumeRepository().patch(id, input),
    onSuccess: (branch) => {
      qc.invalidateQueries({ queryKey: BRANCHES_KEY })
      qc.setQueryData(BRANCH_KEY(branch.id), branch)
    },
  })
}

export function useDeleteBranch() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (id) => getResumeRepository().delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: BRANCHES_KEY }),
  })
}

export function useCreateBlock(branchId: string) {
  const qc = useQueryClient()
  return useMutation<ResumeBlock, Error, CreateBlockInput>({
    mutationFn: (input) => getResumeBlockRepository().create(branchId, input),
    onSuccess: (block) => {
      qc.setQueryData<ResumeBlock[]>(BLOCKS_KEY(branchId), (prev) =>
        prev ? [...prev, block] : [block],
      )
    },
  })
}

export function usePatchBlock(branchId: string) {
  const qc = useQueryClient()
  return useMutation<ResumeBlock, Error, { id: string; input: PatchBlockInput }>({
    mutationFn: ({ id, input }) => getResumeBlockRepository().patch(id, input),
    onSuccess: (block) => {
      qc.setQueryData<ResumeBlock[]>(BLOCKS_KEY(branchId), (prev) =>
        prev ? prev.map((b) => (b.id === block.id ? block : b)) : [block],
      )
    },
  })
}

export function useReorderBlocks(branchId: string) {
  const qc = useQueryClient()
  return useMutation<ResumeBlock, Error, { id: string; input: ReorderBlocksInput }>({
    mutationFn: ({ id, input }) => getResumeBlockRepository().reorder(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: BLOCKS_KEY(branchId) }),
  })
}

export function useDeleteBlock(branchId: string) {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (id) => getResumeBlockRepository().delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: BLOCKS_KEY(branchId) }),
  })
}

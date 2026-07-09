/**
 * Resume branch + block mutations.
 *
 * 036 Phase A.2 — v1 mutations are no-ops. The v2 editor exposes its
 * own mutations through `@/modules/resume/v2/api`. Hooks here are kept
 * so legacy call sites keep importing cleanly until they migrate.
 */
import { useMutation } from '@tanstack/react-query'
import type {
  CreateBlockInput,
  CreateBranchInput,
  PatchBlockInput,
  PatchBranchInput,
  ReorderBlocksInput,
  ResumeBlock,
  ResumeBranch,
} from '@/modules/resume/api/types'

const noop = <T,>(_input: T): Promise<ResumeBranch> =>
  Promise.reject(new Error('v1 resume branches retired (036 Phase A.2)'))

const noopBlock = <T,>(_input: T): Promise<ResumeBlock> =>
  Promise.reject(new Error('v1 resume blocks retired (036 Phase A.2)'))

export function useCreateBranch() {
  return useMutation<ResumeBranch, Error, CreateBranchInput>({
    mutationFn: (input) => noop(input),
  })
}

export function usePatchBranch() {
  return useMutation<ResumeBranch, Error, { id: string; input: PatchBranchInput }>({
    mutationFn: ({ id, input }) => noop({ id, input }),
  })
}

export function useDeleteBranch() {
  return useMutation<void, Error, string>({
    mutationFn: (id) => Promise.reject(new Error('v1 resume branches retired (036 Phase A.2)')),
  })
}

export function useCreateBlock(_branchId: string) {
  return useMutation<ResumeBlock, Error, CreateBlockInput>({
    mutationFn: (input) => noopBlock(input),
  })
}

export function usePatchBlock(_branchId: string) {
  return useMutation<ResumeBlock, Error, { id: string; input: PatchBlockInput }>({
    mutationFn: ({ id, input }) => noopBlock({ id, input }),
  })
}

export function useReorderBlocks(_branchId: string) {
  return useMutation<ResumeBlock, Error, { id: string; input: ReorderBlocksInput }>({
    mutationFn: ({ id, input }) => noopBlock({ id, input }),
  })
}

export function useDeleteBlock(_branchId: string) {
  return useMutation<void, Error, string>({
    mutationFn: (id) => Promise.reject(new Error('v1 resume blocks retired (036 Phase A.2)')),
  })
}
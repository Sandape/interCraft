/**
 * Branch avatar mutation hooks (spec 027 US9).
 *
 * Mutations:
 * - useUploadBranchAvatar(branchId)
 * - useDeleteBranchAvatar(branchId)
 * - useInheritBranchAvatar(branchId)
 *
 * On success, invalidate BRANCHES_KEY + BRANCH_KEY(branchId) so the editor
 * re-renders with the new avatar_url/size/position/shape. Avatar file bytes
 * are served by GET /avatar which is owner-only and short-cached.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  deleteBranchAvatar,
  inheritBranchAvatar,
  uploadBranchAvatar,
  type BranchAvatarOkResponse,
  type BranchAvatarUploadResponse,
} from '../api/avatar'
import { BRANCHES_KEY, BRANCH_KEY } from '../../../hooks/queries/useResumeBranches'

export function useUploadBranchAvatar(branchId: string) {
  const qc = useQueryClient()
  return useMutation<BranchAvatarUploadResponse, Error, File>({
    mutationFn: (file: File) => uploadBranchAvatar(branchId, file),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: BRANCHES_KEY })
      void qc.invalidateQueries({ queryKey: BRANCH_KEY(branchId) })
    },
  })
}

export function useDeleteBranchAvatar(branchId: string) {
  const qc = useQueryClient()
  return useMutation<BranchAvatarOkResponse, Error, void>({
    mutationFn: () => deleteBranchAvatar(branchId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: BRANCHES_KEY })
      void qc.invalidateQueries({ queryKey: BRANCH_KEY(branchId) })
    },
  })
}

export function useInheritBranchAvatar(branchId: string) {
  const qc = useQueryClient()
  return useMutation<BranchAvatarOkResponse, Error, void>({
    mutationFn: () => inheritBranchAvatar(branchId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: BRANCHES_KEY })
      void qc.invalidateQueries({ queryKey: BRANCH_KEY(branchId) })
    },
  })
}
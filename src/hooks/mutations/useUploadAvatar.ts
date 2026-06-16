/**
 * Mutation hooks for avatar upload and remove.
 *
 * Both hooks invalidate the `currentUser` query so the topbar / profile
 * / share dialog / interview live all refetch the new `avatar_url` in
 * the same render cycle.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadAvatar, removeAvatar, type AvatarOut, type AvatarRemoveResponse } from '../../api/avatar'
import { CURRENT_USER_KEY } from '../queries/useCurrentUser'

export function useUploadAvatar() {
  const qc = useQueryClient()
  return useMutation<AvatarOut, Error, File>({
    mutationFn: (file: File) => uploadAvatar(file),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: CURRENT_USER_KEY })
    },
  })
}

export function useRemoveAvatar() {
  const qc = useQueryClient()
  return useMutation<AvatarRemoveResponse, Error, void>({
    mutationFn: () => removeAvatar(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: CURRENT_USER_KEY })
    },
  })
}

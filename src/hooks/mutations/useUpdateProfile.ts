/** Mutation hook for profile update (US11). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { PatchUserInput } from '../../repositories/AccountRepository'
import type { PublicUser } from '../../api/types'
import { getAccountRepository } from '../../repositories/types'
import { CURRENT_USER_KEY } from '../queries/useCurrentUser'

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: PatchUserInput) => getAccountRepository().updateMe(input),
    onSuccess: (data: PublicUser) => {
      qc.setQueryData(CURRENT_USER_KEY, data)
    },
  })
}

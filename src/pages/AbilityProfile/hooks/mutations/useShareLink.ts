/** Mutation hooks for share link operations. */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createShareLink, revokeShareLink } from '@/api/abilityProfileClient'

export function useCreateShareLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ expiresInHours }: { expiresInHours?: number }) =>
      createShareLink(expiresInHours),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shareLinks'] })
    },
  })
}

export function useRevokeShareLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (linkId: string) => revokeShareLink(linkId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shareLinks'] })
    },
  })
}

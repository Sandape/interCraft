/** Mutation hook for patching ability dimensions (US5). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { AbilityDimension } from '../../repositories/AbilityRepository'
import { getAbilityRepository } from '../../repositories/types'

export function usePatchAbility() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, patch }: { key: string; patch: Record<string, unknown> }) =>
      getAbilityRepository().patch(key, patch),
    onSuccess: (data: AbilityDimension) => {
      qc.setQueryData(['ability', data.dimension_key], data)
      qc.invalidateQueries({ queryKey: ['abilities'] })
    },
  })
}

export function useToggleAbility() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, isActive }: { key: string; isActive: boolean }) =>
      getAbilityRepository().toggle(key, isActive),
    onSuccess: (data: AbilityDimension) => {
      qc.setQueryData(['ability', data.dimension_key], data)
      qc.invalidateQueries({ queryKey: ['abilities'] })
    },
  })
}

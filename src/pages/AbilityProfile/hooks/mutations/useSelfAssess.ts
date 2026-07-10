/** Mutation hook for self-assessment (dual-track: writes self_assessed_score). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { getAbilityRepository } from '@/repositories/types'

export function useSelfAssess() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      key,
      score,
      notes,
    }: {
      key: string
      score: number
      notes?: string
    }) =>
      getAbilityRepository().patch(key, {
        self_assessed_score: score,
        ...(notes ? { notes } : {}),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['abilityDashboard'] })
      qc.invalidateQueries({ queryKey: ['abilities'] })
    },
  })
}

/** Mutation hook for self-assessment. */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { getAbilityRepository } from '@/repositories/types'

export function useSelfAssess() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, score }: { key: string; score: number }) =>
      getAbilityRepository().patch(key, { actual_score: score, source: 'manual' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['abilityDashboard'] })
      qc.invalidateQueries({ queryKey: ['abilities'] })
    },
  })
}

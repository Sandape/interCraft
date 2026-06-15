/** React Query hooks for ability dimensions (US5). */
import { useQuery } from '@tanstack/react-query'
import type { AbilityDimension } from '../../repositories/AbilityRepository'
import { getAbilityRepository } from '../../repositories/types'

export function useAbilities(isActive?: boolean) {
  return useQuery<{ data: AbilityDimension[] }>({
    queryKey: ['abilities', isActive],
    queryFn: () => getAbilityRepository().list(isActive),
    staleTime: 60_000,
  })
}

export function useAbility(key: string) {
  return useQuery<AbilityDimension>({
    queryKey: ['ability', key],
    queryFn: () => getAbilityRepository().get(key),
    staleTime: 60_000,
    enabled: !!key,
  })
}

export function useAbilityHistory(
  dimensionKey?: string,
  aggregate: 'month' | 'day' = 'month',
  from?: string,
  to?: string,
) {
  return useQuery({
    queryKey: ['abilityHistory', dimensionKey, aggregate, from, to],
    queryFn: () => getAbilityRepository().history(dimensionKey, aggregate, from, to),
    staleTime: 120_000,
  })
}

export function useDimensionsMeta() {
  return useQuery({
    queryKey: ['dimensionsMeta'],
    queryFn: () => getAbilityRepository().dimensionsMeta(),
    staleTime: Infinity,
  })
}

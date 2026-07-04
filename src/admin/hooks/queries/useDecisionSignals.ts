/**
 * React Query hooks for the command-center decision signals (REQ-044 US1).
 */
import { useQuery } from '@tanstack/react-query'
import {
  adminCommandCenterApi,
  type DecisionSignalsListParams,
} from '@/api/admin-decision-signals'

export const decisionSignalsQueryKey = (params: DecisionSignalsListParams = {}) =>
  ['command-center', 'decision-signals', params] as const

export function useDecisionSignals(params: DecisionSignalsListParams = {}) {
  return useQuery({
    queryKey: decisionSignalsQueryKey(params),
    queryFn: ({ signal }) => adminCommandCenterApi.listSignals(params, signal),
    staleTime: 60_000,
  })
}

export function useCommandCenterOverview() {
  return useQuery({
    queryKey: ['command-center', 'overview'] as const,
    queryFn: ({ signal }) => adminCommandCenterApi.getOverview(signal),
    staleTime: 60_000,
  })
}
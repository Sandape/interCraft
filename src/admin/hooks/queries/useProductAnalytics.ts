/**
 * React Query hooks for Product Analytics workspace — REQ-044 US2.
 */
import { useQuery } from '@tanstack/react-query'
import {
  adminProductAnalyticsApi,
  type FeatureAdoptionParams,
  type FunnelParams,
} from '@/api/admin-product-analytics'

export const productAnalyticsQueryKeys = {
  questionTemplates: () =>
    ['product-analytics', 'question-templates'] as const,
  funnel: (params: FunnelParams) =>
    ['product-analytics', 'funnel', params] as const,
  cohorts: () => ['product-analytics', 'cohorts'] as const,
  featureAdoption: (params: FeatureAdoptionParams) =>
    ['product-analytics', 'feature-adoption', params] as const,
  health: () => ['product-analytics', 'health'] as const,
}

export function useQuestionTemplates() {
  return useQuery({
    queryKey: productAnalyticsQueryKeys.questionTemplates(),
    queryFn: ({ signal }) =>
      adminProductAnalyticsApi.listQuestionTemplates({}, signal),
    staleTime: 60_000,
  })
}

export function useFunnel(params: FunnelParams = {}) {
  return useQuery({
    queryKey: productAnalyticsQueryKeys.funnel(params),
    queryFn: ({ signal }) => adminProductAnalyticsApi.getFunnel(params, signal),
    staleTime: 60_000,
  })
}

export function useCohorts() {
  return useQuery({
    queryKey: productAnalyticsQueryKeys.cohorts(),
    queryFn: ({ signal }) => adminProductAnalyticsApi.listCohorts(signal),
    staleTime: 60_000,
  })
}

export function useFeatureAdoption(params: FeatureAdoptionParams = {}) {
  return useQuery({
    queryKey: productAnalyticsQueryKeys.featureAdoption(params),
    queryFn: ({ signal }) =>
      adminProductAnalyticsApi.getFeatureAdoption(params, signal),
    staleTime: 60_000,
  })
}

export function useProductAnalyticsHealth() {
  return useQuery({
    queryKey: productAnalyticsQueryKeys.health(),
    queryFn: ({ signal }) => adminProductAnalyticsApi.getHealth(signal),
    staleTime: 30_000,
  })
}
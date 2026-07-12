/**
 * React Query hooks for AI Operations — REQ-044 legacy + REQ-061 T120 real metrics.
 */
import { useQuery } from '@tanstack/react-query'
import {
  adminAIOperationsApi,
  type LatencyBandsParams,
  type VolumeByFeatureParams,
} from '@/api/admin-ai-operations'
import {
  aiOperationsApi,
  defaultMetricsFilters,
  type MetricsFilters,
  type OpsFilters,
} from '@/admin/api/ai-operations'

export { defaultMetricsFilters }
export type { MetricsFilters }

export const aiOperationsQueryKeys = {
  kpis: () => ['ai-operations', 'kpis'] as const,
  volumeByFeature: (params: VolumeByFeatureParams) =>
    ['ai-operations', 'volume-by-feature', params] as const,
  failureCategories: () => ['ai-operations', 'failure-categories'] as const,
  latencyBands: (params: LatencyBandsParams) =>
    ['ai-operations', 'latency-bands', params] as const,
  tokenUsage: () => ['ai-operations', 'token-usage'] as const,
  costSummary: () => ['ai-operations', 'cost-summary'] as const,
  versionSelector: () => ['ai-operations', 'version-selector'] as const,
  qualityIssues: () => ['ai-operations', 'quality-issues'] as const,
  costQualityFlag: () => ['ai-operations', 'cost-quality-flag'] as const,
  evalBadcaseSummary: () => ['ai-operations', 'eval-badcase-summary'] as const,
  health: () => ['ai-operations', 'health'] as const,
}

export const aiOpsKeys = {
  all: ['admin', 'ai-operations'] as const,
  metrics: (filters: OpsFilters) => [...aiOpsKeys.all, 'metrics', filters] as const,
  costDrilldown: (filters: OpsFilters & { task_id?: string }) =>
    [...aiOpsKeys.all, 'cost-drilldown', filters] as const,
  pointTimeline: (taskId: string) => [...aiOpsKeys.all, 'point-timeline', taskId] as const,
  productionMetrics: (filters: MetricsFilters) =>
    [...aiOpsKeys.all, 'production-metrics', filters] as const,
  budgets: () => [...aiOpsKeys.all, 'budgets'] as const,
  reconciliations: () => [...aiOpsKeys.all, 'reconciliations'] as const,
  anomalies: () => [...aiOpsKeys.all, 'anomalies'] as const,
  taskCostDrilldown: (taskId: string) =>
    [...aiOpsKeys.all, 'task-cost-drilldown', taskId] as const,
}

export function useKpis() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.kpis(),
    queryFn: ({ signal }) => adminAIOperationsApi.getKpis(signal),
    staleTime: 60_000,
  })
}

export function useVolumeByFeature(params: VolumeByFeatureParams = {}) {
  return useQuery({
    queryKey: aiOperationsQueryKeys.volumeByFeature(params),
    queryFn: ({ signal }) =>
      adminAIOperationsApi.getVolumeByFeature(params, signal),
    staleTime: 60_000,
  })
}

export function useFailureCategories() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.failureCategories(),
    queryFn: ({ signal }) =>
      adminAIOperationsApi.getFailureCategories(signal),
    staleTime: 60_000,
  })
}

export function useLatencyBands(params: LatencyBandsParams = {}) {
  return useQuery({
    queryKey: aiOperationsQueryKeys.latencyBands(params),
    queryFn: ({ signal }) => adminAIOperationsApi.getLatencyBands(params, signal),
    staleTime: 60_000,
  })
}

export function useTokenUsage() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.tokenUsage(),
    queryFn: ({ signal }) => adminAIOperationsApi.getTokenUsage(signal),
    staleTime: 60_000,
  })
}

export function useCostSummary() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.costSummary(),
    queryFn: ({ signal }) => adminAIOperationsApi.getCostSummary(signal),
    staleTime: 60_000,
  })
}

export function useVersionSelector() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.versionSelector(),
    queryFn: ({ signal }) =>
      adminAIOperationsApi.getVersionSelector(signal),
    staleTime: 60_000,
  })
}

export function useQualityIssues() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.qualityIssues(),
    queryFn: ({ signal }) => adminAIOperationsApi.getQualityIssues(signal),
    staleTime: 60_000,
  })
}

export function useCostQualityFlag() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.costQualityFlag(),
    queryFn: ({ signal }) => adminAIOperationsApi.getCostQualityFlag(signal),
    staleTime: 60_000,
  })
}

export function useEvalBadcaseSummary() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.evalBadcaseSummary(),
    queryFn: ({ signal }) =>
      adminAIOperationsApi.getEvalBadcaseSummary(signal),
    staleTime: 60_000,
  })
}

export function useAIOperationsHealth() {
  return useQuery({
    queryKey: aiOperationsQueryKeys.health(),
    queryFn: ({ signal }) => adminAIOperationsApi.getHealth(signal),
    staleTime: 30_000,
  })
}

/** REQ-061 — fact-joined metrics with filters + data quality. */
export function useAIOpsMetrics(filters: OpsFilters = {}) {
  return useQuery({
    queryKey: aiOpsKeys.metrics(filters),
    queryFn: ({ signal }) => aiOperationsApi.getMetrics(filters, signal),
    staleTime: 30_000,
  })
}

export function useAIOpsCostDrilldown(
  filters: OpsFilters & { task_id?: string } = {},
  enabled = true,
) {
  return useQuery({
    queryKey: aiOpsKeys.costDrilldown(filters),
    queryFn: ({ signal }) => aiOperationsApi.getCostDrilldown(filters, signal),
    enabled,
    staleTime: 15_000,
  })
}

export function useAIOpsPointTimeline(taskId: string | null) {
  return useQuery({
    queryKey: aiOpsKeys.pointTimeline(taskId ?? ''),
    queryFn: ({ signal }) => aiOperationsApi.getPointTimeline(taskId as string, signal),
    enabled: Boolean(taskId),
    staleTime: 15_000,
  })
}

/** REQ-061 US9 — production joined metrics with stable filters. */
export function useProductionMetrics(filters: MetricsFilters = defaultMetricsFilters) {
  return useQuery({
    queryKey: aiOpsKeys.productionMetrics(filters),
    queryFn: ({ signal }) => aiOperationsApi.getProductionMetrics(filters, signal),
    staleTime: 30_000,
  })
}

export function useProductionBudgets() {
  return useQuery({
    queryKey: aiOpsKeys.budgets(),
    queryFn: ({ signal }) => aiOperationsApi.listBudgets(signal),
    staleTime: 30_000,
  })
}

export function useProductionReconciliations() {
  return useQuery({
    queryKey: aiOpsKeys.reconciliations(),
    queryFn: ({ signal }) => aiOperationsApi.listReconciliations(signal),
    staleTime: 30_000,
  })
}

export function useProductionAnomalies() {
  return useQuery({
    queryKey: aiOpsKeys.anomalies(),
    queryFn: ({ signal }) => aiOperationsApi.listAnomalies(signal),
    staleTime: 30_000,
  })
}

export function useTaskCostDrilldown(taskId: string | null) {
  return useQuery({
    queryKey: aiOpsKeys.taskCostDrilldown(taskId ?? ''),
    queryFn: ({ signal }) =>
      aiOperationsApi.getTaskCostDrilldown(taskId as string, signal),
    enabled: Boolean(taskId),
    staleTime: 15_000,
  })
}

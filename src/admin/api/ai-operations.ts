/**
 * REQ-061 T120 — AI operations client (admin-console/ai-operations).
 * Production metrics / budgets / reconciliations / anomalies / cost drilldown.
 */
import { apiClient } from '@/api/client'

const BASE = '/api/v1/admin-console/ai-operations'

export interface DataQuality {
  fresh_at: string | null
  coverage_percent: number | null
  unknown_count: number
  seed_or_mock_count: number
}

export interface DecimalMoney {
  amount: string
  currency: string
}

/** Filters used by the production metrics surface (US9). */
export interface MetricsFilters {
  capability?: string
  serviceTier?: '' | 'standard' | 'quality'
  policyVersion?: string
  releaseBatch?: string
  from?: string
  to?: string
}

export const defaultMetricsFilters: MetricsFilters = {
  capability: '',
  serviceTier: '',
  policyVersion: '',
  releaseBatch: '',
}

export interface MetricsResponse {
  stability: { success_rate?: number | null; [key: string]: unknown }
  quality: { badcase_rate?: number | null; badcase_open?: number | null; [key: string]: unknown }
  latency: { p95_ms?: number | null; [key: string]: unknown }
  points: { settled_total?: number | null; [key: string]: unknown }
  cost: { rmb_total?: string | null; unknown_cost_events?: number | null; [key: string]: unknown }
  revenue_rmb: DecimalMoney
  data_quality: DataQuality
}

export interface BudgetItem {
  budget_id: string
  scope_type: string
  scope_ref: string
  period: string
  amount_rmb: DecimalMoney
  consumed_rmb: DecimalMoney
  utilization_percent: string
  level: string
  warning_reached: boolean
  hard_limit_reached: boolean
  stop_new_optional_tasks: boolean
}

export interface ReconciliationItem {
  run_type: string
  status: string
  expected_total?: string | null
  actual_total?: string | null
  difference?: string | null
  difference_pct?: string | null
  issue_count: number
  issues?: Array<Record<string, unknown>>
}

export interface AnomaliesResponse {
  items: Array<Record<string, unknown>>
  protected_operations: string[]
}

export interface TaskCostAttempt {
  attempt_id: string
  attempt_kind?: string
  cost_status: string
  cost?: DecimalMoney | null
  cost_rate_version?: string | null
  adjustment?: string | null
  [key: string]: unknown
}

export interface TaskCostMilestone {
  milestone?: string
  occurred_at?: string
  points?: number | null
  cost_rmb?: string | null
  [key: string]: unknown
}

export interface TaskCostDrilldown {
  task_id: string
  point_settled: number
  cost_status: string
  current_cost_rmb: DecimalMoney
  attempts: TaskCostAttempt[]
  milestones: TaskCostMilestone[]
  data_quality: DataQuality
}

/** @deprecated Alias kept for useAIOps* callers. */
export type OpsFilters = {
  capability?: string | null
  service_tier?: string | null
  from?: string | null
  to?: string | null
  cursor?: string | null
}

/** @deprecated Alias — prefer MetricsResponse. */
export type MetricsBundle = MetricsResponse & {
  costs?: {
    confirmed_rmb?: string | null
    estimated_rmb?: string | null
    beta_revenue_rmb: string
    unknown_count: number
  }
  budgets?: Array<{ scope: string; used_percent: number; status: string }>
  anomalies?: Array<{ code: string; message: string }>
}

export interface CostAttemptRow {
  attempt_id: string
  task_id: string
  milestone_code?: string | null
  provider_status?: string | null
  cost_status: string
  cost_rmb?: string | null
  points_settled?: number | null
}

export interface CostDrilldownPage {
  items: CostAttemptRow[]
  next_cursor?: string | null
  data_quality: DataQuality
}

function metricsQuery(filters: MetricsFilters = {}) {
  return {
    capability: filters.capability || undefined,
    service_tier: filters.serviceTier || undefined,
    policy_version: filters.policyVersion || undefined,
    release_batch: filters.releaseBatch || undefined,
    from: filters.from || undefined,
    to: filters.to || undefined,
  }
}

function opsFilterQuery(filters: OpsFilters = {}) {
  return {
    capability: filters.capability ?? undefined,
    service_tier: filters.service_tier ?? undefined,
    from: filters.from ?? undefined,
    to: filters.to ?? undefined,
    cursor: filters.cursor ?? undefined,
  }
}

export const aiOperationsApi = {
  getProductionMetrics: (filters: MetricsFilters = {}, signal?: AbortSignal) =>
    apiClient.request<MetricsResponse>({
      method: 'GET',
      path: `${BASE}/metrics`,
      query: metricsQuery(filters),
      signal,
    }),

  listBudgets: (signal?: AbortSignal) =>
    apiClient.request<{ items: BudgetItem[] }>({
      method: 'GET',
      path: `${BASE}/budgets`,
      signal,
    }),

  listReconciliations: (signal?: AbortSignal) =>
    apiClient.request<{ items: ReconciliationItem[]; data_quality?: Partial<DataQuality> }>({
      method: 'GET',
      path: `${BASE}/reconciliations`,
      signal,
    }),

  listAnomalies: (signal?: AbortSignal) =>
    apiClient.request<AnomaliesResponse>({
      method: 'GET',
      path: `${BASE}/anomalies`,
      signal,
    }),

  getTaskCostDrilldown: (taskId: string, signal?: AbortSignal) =>
    apiClient.request<TaskCostDrilldown>({
      method: 'GET',
      path: `${BASE}/tasks/${encodeURIComponent(taskId)}/cost-drilldown`,
      signal,
    }),

  /** Legacy T120 shape — maps onto production metrics. */
  getMetrics: (filters: OpsFilters = {}, signal?: AbortSignal) =>
    apiClient.request<MetricsBundle>({
      method: 'GET',
      path: `${BASE}/metrics`,
      query: opsFilterQuery(filters),
      signal,
    }),

  getCostDrilldown: (filters: OpsFilters & { task_id?: string } = {}, signal?: AbortSignal) =>
    apiClient.request<CostDrilldownPage>({
      method: 'GET',
      path: `${BASE}/costs/attempts`,
      query: { ...opsFilterQuery(filters), task_id: filters.task_id },
      signal,
    }),

  getPointTimeline: (taskId: string, signal?: AbortSignal) =>
    apiClient.request<{
      items: Array<{
        event_id: string
        milestone_code?: string | null
        points: number
        kind: string
        at: string
      }>
      data_quality: DataQuality
    }>({
      method: 'GET',
      path: `${BASE}/tasks/${encodeURIComponent(taskId)}/point-timeline`,
      signal,
    }),
}

export default aiOperationsApi

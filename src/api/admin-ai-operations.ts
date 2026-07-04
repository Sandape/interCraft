/**
 * Admin Console / AI Operations API client — REQ-044 US3.
 *
 * Endpoints (mounted by backend/app/main.py at prefix
 * `/api/v1/admin-console/ai-operations`):
 *
 * - GET /kpis
 * - GET /volume-by-feature
 * - GET /failure-categories
 * - GET /latency-bands
 * - GET /token-usage
 * - GET /cost-summary
 * - GET /version-selector
 * - GET /quality-issues
 * - GET /cost-quality-flag
 * - GET /eval-badcase-summary
 * - GET /health
 *
 * The seed-driven backend (US3) returns static + internally consistent
 * payloads; Phase 2 batch 3 wires the real AIInvocationRecord +
 * eval + badcases aggregations.
 */
import { apiClient } from './client'
import type {
  AIQualityIssueListResponse,
  CostQualityFlag,
  CostSummaryResponse,
  EvalBadcaseSummary,
  FailureCategoryResponse,
  KPIBundleResponse,
  LatencyBands,
  TokenUsageResponse,
  VersionSelectorResponse,
  VolumeByFeatureResponse,
} from '../types/admin-ai-operations'

const BASE = '/api/v1/admin-console/ai-operations'

export interface VolumeByFeatureParams {
  featureArea?: string | null
}

export interface LatencyBandsParams {
  featureArea?: string | null
}

export const adminAIOperationsApi = {
  /** FR-016 + AC-16.1 — 4 KPI tiles. */
  getKpis: (signal?: AbortSignal) =>
    apiClient.request<KPIBundleResponse>({
      method: 'GET',
      path: `${BASE}/kpis`,
      signal,
    }),

  /** FR-016 + AC-16.2 — per-area call / success / failure. */
  getVolumeByFeature: (
    params: VolumeByFeatureParams = {},
    signal?: AbortSignal,
  ) =>
    apiClient.request<VolumeByFeatureResponse>({
      method: 'GET',
      path: `${BASE}/volume-by-feature`,
      query: { feature_area: params.featureArea ?? undefined },
      signal,
    }),

  /** FR-016 + AC-16.3 — failure category breakdown. */
  getFailureCategories: (signal?: AbortSignal) =>
    apiClient.request<FailureCategoryResponse>({
      method: 'GET',
      path: `${BASE}/failure-categories`,
      signal,
    }),

  /** FR-016 + AC-16.4 — p50/p95/p99 per FeatureArea. */
  getLatencyBands: (
    params: LatencyBandsParams = {},
    signal?: AbortSignal,
  ) =>
    apiClient.request<LatencyBands>({
      method: 'GET',
      path: `${BASE}/latency-bands`,
      query: { feature_area: params.featureArea ?? undefined },
      signal,
    }),

  /** FR-016 + AC-16.5 — input vs output tokens per FeatureArea. */
  getTokenUsage: (signal?: AbortSignal) =>
    apiClient.request<TokenUsageResponse>({
      method: 'GET',
      path: `${BASE}/token-usage`,
      signal,
    }),

  /** FR-016 + AC-16.6 + EC-3 — total + per-area USD cost. */
  getCostSummary: (signal?: AbortSignal) =>
    apiClient.request<CostSummaryResponse>({
      method: 'GET',
      path: `${BASE}/cost-summary`,
      signal,
    }),

  /** FR-017 + AC-17.1 + EC-2 — version dimensions availability. */
  getVersionSelector: (signal?: AbortSignal) =>
    apiClient.request<VersionSelectorResponse>({
      method: 'GET',
      path: `${BASE}/version-selector`,
      signal,
    }),

  /** FR-018 + AC-18.1/18.2 — AI quality issue list with 8 link fields. */
  getQualityIssues: (signal?: AbortSignal) =>
    apiClient.request<AIQualityIssueListResponse>({
      method: 'GET',
      path: `${BASE}/quality-issues`,
      signal,
    }),

  /** FR-019 + AC-19.1/19.2 — cost-quality tradeoff flag. */
  getCostQualityFlag: (signal?: AbortSignal) =>
    apiClient.request<CostQualityFlag>({
      method: 'GET',
      path: `${BASE}/cost-quality-flag`,
      signal,
    }),

  /** FR-020 + AC-20.1/20.2 — eval + badcase summary card. */
  getEvalBadcaseSummary: (signal?: AbortSignal) =>
    apiClient.request<EvalBadcaseSummary>({
      method: 'GET',
      path: `${BASE}/eval-badcase-summary`,
      signal,
    }),

  /** Module liveness. */
  getHealth: (signal?: AbortSignal) =>
    apiClient.request<{ status: string; module: string }>({
      method: 'GET',
      path: `${BASE}/health`,
      signal,
    }),
}

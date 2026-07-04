/**
 * Admin Console / Product Analytics API client — REQ-044 US2.
 *
 * Endpoints (mounted by backend/app/main.py):
 *
 * - GET /api/v1/admin-console/product-analytics/question-templates
 * - GET /api/v1/admin-console/product-analytics/funnel?template_id&cohort_id
 * - GET /api/v1/admin-console/product-analytics/cohorts
 * - GET /api/v1/admin-console/product-analytics/feature-adoption?cohort_id
 * - GET /api/v1/admin-console/product-analytics/health
 */
import { apiClient } from './client'
import type {
  CohortListResponse,
  FeatureAdoptionResponse,
  FunnelResponse,
  QuestionTemplateListResponse,
} from '../types/admin-product-analytics'

const BASE = '/api/v1/admin-console/product-analytics'

export interface QuestionTemplatesParams {
  // none for now — endpoint is a flat list
}

export interface FunnelParams {
  templateId?: string
  cohortId?: string | null
  periodStart?: string | null
  periodEnd?: string | null
}

export interface FeatureAdoptionParams {
  cohortId?: string | null
}

export const adminProductAnalyticsApi = {
  /** FR-011 — ≥21 question templates (3 per tab × 7 tabs). */
  listQuestionTemplates: (
    _params: QuestionTemplatesParams = {},
    signal?: AbortSignal,
  ) =>
    apiClient.request<QuestionTemplateListResponse>({
      method: 'GET',
      path: `${BASE}/question-templates`,
      signal,
    }),

  /** FR-012 — 5-step funnel with conversion + drop-off + time-to-convert. */
  getFunnel: (params: FunnelParams = {}, signal?: AbortSignal) =>
    apiClient.request<FunnelResponse>({
      method: 'GET',
      path: `${BASE}/funnel`,
      query: {
        template_id: params.templateId ?? 'q-fun-1',
        cohort_id: params.cohortId ?? undefined,
        period_start: params.periodStart ?? undefined,
        period_end: params.periodEnd ?? undefined,
      },
      signal,
    }),

  /** FR-013 — cohort list. */
  listCohorts: (signal?: AbortSignal) =>
    apiClient.request<CohortListResponse>({
      method: 'GET',
      path: `${BASE}/cohorts`,
      signal,
    }),

  /** FR-014 — 5-metric feature adoption grid. */
  getFeatureAdoption: (
    params: FeatureAdoptionParams = {},
    signal?: AbortSignal,
  ) =>
    apiClient.request<FeatureAdoptionResponse>({
      method: 'GET',
      path: `${BASE}/feature-adoption`,
      query: {
        cohort_id: params.cohortId ?? undefined,
      },
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
/**
 * REQ-061 US10 — production Bad Case management API client (T137).
 *
 * Canonical facade: `/api/v1/admin-console/ai/badcases*`.
 * Seed/mock rows are forbidden (`data_quality.seed_or_mock_count === 0`).
 */
import { apiClient } from '@/api/client'

const BASE = '/api/v1/admin-console/ai'

export type DataQuality = {
  fresh_at: string
  coverage_percent: number
  unknown_count: number
  seed_or_mock_count: number
}

export type OperationalBadcaseSummary = {
  badcase_id: string
  status: string
  severity: string
  category: string
  capabilities: string[]
  owner: string | null
  privacy_class: string
  first_seen_at: string | null
  last_seen_at: string | null
  task_count: number
  user_count: number | null
  user_count_status: string
  point_treatment_status: string
  sla_status: string
  version: number
  data_completeness: string
}

export type OperationalBadcasePage = {
  items: OperationalBadcaseSummary[]
  next_cursor: string | null
  data_quality: DataQuality
  compatibility?: Record<string, string>
}

export type BadcaseListFilters = {
  status?: string
  severity?: string
  category?: string
  capability?: string
  owner?: string
  privacy_class?: string
  point_treatment_status?: string
  sla_status?: string
  cursor?: string
  limit?: number
}

export type ImpactConfidence = 'confirmed' | 'possible' | 'excluded' | 'unknown'

export type BadcaseImpact = {
  impact_id: string
  impact_kind: string
  subject_ref: string
  confidence: ImpactConfidence
  first_seen_at: string | null
  last_updated_at: string | null
  evidence_refs: Array<Record<string, unknown>>
  version: number
}

export type BadcaseActionCommand = {
  action_type: string
  expected_version: number
  reason: string
  [key: string]: unknown
}

function toQuery(filters: BadcaseListFilters = {}): Record<string, string | number | undefined> {
  return {
    status: filters.status,
    severity: filters.severity,
    category: filters.category,
    capability: filters.capability,
    owner: filters.owner,
    privacy_class: filters.privacy_class,
    point_treatment_status: filters.point_treatment_status,
    sla_status: filters.sla_status,
    cursor: filters.cursor,
    limit: filters.limit,
  }
}

export const productionBadcasesApi = {
  list: (filters: BadcaseListFilters = {}, signal?: AbortSignal) =>
    apiClient.request<OperationalBadcasePage>({
      method: 'GET',
      path: `${BASE}/badcases`,
      query: toQuery(filters),
      signal,
    }),

  get: (badcaseId: string, signal?: AbortSignal) =>
    apiClient.request<Record<string, unknown>>({
      method: 'GET',
      path: `${BASE}/badcases/${encodeURIComponent(badcaseId)}`,
      signal,
    }),

  timeline: (badcaseId: string, signal?: AbortSignal) =>
    apiClient.request<{ items: Array<Record<string, unknown>>; data_quality: DataQuality }>({
      method: 'GET',
      path: `${BASE}/badcases/${encodeURIComponent(badcaseId)}/timeline`,
      signal,
    }),

  impacts: (
    badcaseId: string,
    opts: { confidence?: ImpactConfidence; impact_kind?: string } = {},
    signal?: AbortSignal,
  ) =>
    apiClient.request<{ items: BadcaseImpact[]; data_quality: DataQuality }>({
      method: 'GET',
      path: `${BASE}/badcases/${encodeURIComponent(badcaseId)}/impacts`,
      query: {
        confidence: opts.confidence,
        impact_kind: opts.impact_kind,
      },
      signal,
    }),

  action: (
    badcaseId: string,
    command: BadcaseActionCommand,
    idempotencyKey: string,
    signal?: AbortSignal,
  ) =>
    apiClient.request<Record<string, unknown>>({
      method: 'POST',
      path: `${BASE}/badcases/${encodeURIComponent(badcaseId)}/actions`,
      body: command,
      headers: { 'Idempotency-Key': idempotencyKey },
      signal,
    }),
}

/**
 * REQ-061 T109 — admin model policy list/detail/candidate/traffic/evidence/rollback.
 */
import { apiClient } from '@/api/client'

const BASE = '/api/v1/admin-console/ai/model-policies'

export interface ModelPolicySummary {
  policy_version: string
  capability: string
  subscenario?: string
  service_tier: 'standard' | 'quality' | string
  status: 'draft' | 'candidate' | 'gray' | 'stable' | 'stopped' | 'retired' | string
  traffic_percent?: number
  primary_route?: string
  allowed_fallbacks?: string[]
  rollback_target?: string | null
  owner?: string
  eval_evidence_ref?: string | null
  cost_ceiling_rmb?: string | number | null
  effective_from?: string | null
  effective_to?: string | null
}

export interface ModelPolicyPage {
  items: ModelPolicySummary[]
  next_cursor?: string | null
}

export interface ModelPolicyReleaseBody {
  target_status: 'gray' | 'stable' | 'stopped' | 'retired'
  traffic_percent: number
  eval_evidence_ref: string
  rollback_target: string
  reason: string
}

export const aiModelPoliciesApi = {
  list: (signal?: AbortSignal) =>
    apiClient.request<ModelPolicyPage>({
      method: 'GET',
      path: BASE,
      signal,
    }),

  get: (policyVersion: string, signal?: AbortSignal) =>
    apiClient.request<ModelPolicySummary>({
      method: 'GET',
      path: `${BASE}/${encodeURIComponent(policyVersion)}`,
      signal,
    }),

  create: (body: Record<string, unknown>, idempotencyKey: string, signal?: AbortSignal) =>
    apiClient.request<ModelPolicySummary>({
      method: 'POST',
      path: BASE,
      body,
      headers: { 'Idempotency-Key': idempotencyKey },
      signal,
    }),

  release: (
    policyVersion: string,
    body: ModelPolicyReleaseBody,
    idempotencyKey: string,
    signal?: AbortSignal,
  ) =>
    apiClient.request<{ accepted: boolean; policy_version: string }>({
      method: 'POST',
      path: `${BASE}/${encodeURIComponent(policyVersion)}/release`,
      body,
      headers: { 'Idempotency-Key': idempotencyKey },
      signal,
    }),
}

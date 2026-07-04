/**
 * Admin Console Governance / Audit / Export / Retention API client — REQ-044 US6.
 *
 * Endpoints (mounted by ``backend/app/main.py``):
 *
 *   GET    /api/v1/admin-console/governance/access-matrix
 *   POST   /api/v1/admin-console/governance/reveal-requests
 *   GET    /api/v1/admin-console/governance/reveal-requests
 *   GET    /api/v1/admin-console/governance/audit-events
 *   POST   /api/v1/admin-console/governance/exports
 *   GET    /api/v1/admin-console/governance/retention-policy
 *   PUT    /api/v1/admin-console/governance/retention-policy
 *   GET    /api/v1/admin-console/governance/health
 */
import { apiClient } from './client'
import type {
  AccessMatrixResponse,
  AuditAction,
  AuditEventListResponse,
  ExportRequestCreate,
  ExportResponse,
  RevealRequest,
  RevealRequestCreate,
  RevealRequestListResponse,
  RetentionPolicy,
  RetentionPolicyResponse,
  RetentionPolicyUpdate,
} from '../types/admin-governance'

const GOV_BASE = '/api/v1/admin-console/governance'

export const adminGovernanceApi = {
  // --- Access matrix (FR-031 / AC-31.1) ---
  /** FR-031: 5 role × 8 workspace × 6 capability matrix. */
  getAccessMatrix: (signal?: AbortSignal) =>
    apiClient.request<AccessMatrixResponse>({
      method: 'GET',
      path: `${GOV_BASE}/access-matrix`,
      signal,
    }),

  // --- Reveal requests (FR-033 / AC-33.1) ---
  /** POST a sensitive reveal request (requires SENSITIVE_REVEAL). */
  createRevealRequest: (
    body: RevealRequestCreate,
    signal?: AbortSignal,
  ) =>
    apiClient.request<RevealRequest>({
      method: 'POST',
      path: `${GOV_BASE}/reveal-requests`,
      body,
      signal,
    }),

  /** GET reveal-request list (requires AUDIT_VIEW). */
  listRevealRequests: (signal?: AbortSignal) =>
    apiClient.request<RevealRequestListResponse>({
      method: 'GET',
      path: `${GOV_BASE}/reveal-requests`,
      signal,
    }),

  // --- Audit log (FR-034 / AC-34.2) ---
  /** GET audit events (requires AUDIT_VIEW). */
  listAuditEvents: (
    params: { actor?: string; action?: AuditAction } = {},
    signal?: AbortSignal,
  ) => {
    const search = new URLSearchParams()
    if (params.actor) search.set('actor', params.actor)
    if (params.action) search.set('action', params.action)
    const qs = search.toString()
    return apiClient.request<AuditEventListResponse>({
      method: 'GET',
      path: qs ? `${GOV_BASE}/audit-events?${qs}` : `${GOV_BASE}/audit-events`,
      signal,
    })
  },

  // --- Exports (FR-035 / AC-35.1) ---
  /** POST an export (requires EXPORT). */
  createExport: (body: ExportRequestCreate, signal?: AbortSignal) =>
    apiClient.request<ExportResponse>({
      method: 'POST',
      path: `${GOV_BASE}/exports`,
      body,
      signal,
    }),

  // --- Retention policy (FR-036 / AC-36.1 / AC-36.2) ---
  /** GET retention policy list (requires GOVERNANCE_VIEW). */
  listRetentionPolicy: (signal?: AbortSignal) =>
    apiClient.request<RetentionPolicyResponse>({
      method: 'GET',
      path: `${GOV_BASE}/retention-policy`,
      signal,
    }),

  /** PUT retention policy (requires GOVERNANCE_CHANGE). */
  updateRetentionPolicy: (
    body: RetentionPolicyUpdate,
    signal?: AbortSignal,
  ) =>
    apiClient.request<RetentionPolicy>({
      method: 'PUT',
      path: `${GOV_BASE}/retention-policy`,
      body,
      signal,
    }),

  /** Module liveness. */
  getHealth: (signal?: AbortSignal) =>
    apiClient.request<{ status: string; module: string }>({
      method: 'GET',
      path: `${GOV_BASE}/health`,
      signal,
    }),
}

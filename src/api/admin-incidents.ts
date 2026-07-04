/**
 * Admin Console Incidents & Badcases API client — REQ-044 US4.
 *
 * Endpoints (mounted by ``backend/app/main.py``):
 *
 *   GET    /api/v1/admin-console/incidents
 *   GET    /api/v1/admin-console/incidents/{id}
 *   GET    /api/v1/admin-console/incidents/{id}/evidence
 *   GET    /api/v1/admin-console/incidents/{id}/comments
 *   POST   /api/v1/admin-console/incidents/{id}/comments
 *   PATCH  /api/v1/admin-console/incidents/{id}/status
 *   GET    /api/v1/admin-console/incidents/{id}/audit-trail
 *   GET    /api/v1/admin-console/incidents/health
 *   GET    /api/v1/admin-console/badcases
 *   GET    /api/v1/admin-console/badcases/{id}
 *   POST   /api/v1/admin-console/badcases/{id}/escalate
 *   GET    /api/v1/admin-console/badcases/health
 */
import { apiClient } from './client'
import type {
  AuditTrail,
  Badcase,
  BadcaseEscalateResponse,
  BadcaseListResponse,
  Comment,
  CommentCreateRequest,
  CommentListResponse,
  EvidenceLinkListResponse,
  Incident,
  IncidentListResponse,
  StatusChangeRequest,
} from '../types/admin-incidents'

const INCIDENTS_BASE = '/api/v1/admin-console/incidents'
const BADCASES_BASE = '/api/v1/admin-console/badcases'

export const adminIncidentsApi = {
  // --- Incidents ----------------------------------------------------------
  /** FR-021: incident list (10 FR-021 fields + EC-1/2/3 fields). */
  listIncidents: (signal?: AbortSignal) =>
    apiClient.request<IncidentListResponse>({
      method: 'GET',
      path: INCIDENTS_BASE,
      signal,
    }),

  /** AC-21.3: single incident detail. */
  getIncident: (incidentId: string, signal?: AbortSignal) =>
    apiClient.request<Incident>({
      method: 'GET',
      path: `${INCIDENTS_BASE}/${encodeURIComponent(incidentId)}`,
      signal,
    }),

  /** FR-022: 8-type evidence link list. */
  getEvidence: (incidentId: string, signal?: AbortSignal) =>
    apiClient.request<EvidenceLinkListResponse>({
      method: 'GET',
      path: `${INCIDENTS_BASE}/${encodeURIComponent(incidentId)}/evidence`,
      signal,
    }),

  /** FR-022: comment list. */
  listComments: (incidentId: string, signal?: AbortSignal) =>
    apiClient.request<CommentListResponse>({
      method: 'GET',
      path: `${INCIDENTS_BASE}/${encodeURIComponent(incidentId)}/comments`,
      signal,
    }),

  /** FR-022 + AC-22.2: add a comment (requires INCIDENT_CHANGE). */
  addComment: (
    incidentId: string,
    body: CommentCreateRequest,
    signal?: AbortSignal,
  ) =>
    apiClient.request<Comment>({
      method: 'POST',
      path: `${INCIDENTS_BASE}/${encodeURIComponent(incidentId)}/comments`,
      body,
      signal,
    }),

  /** EC-4: PATCH status (requires INCIDENT_CHANGE). */
  changeStatus: (
    incidentId: string,
    body: StatusChangeRequest,
    signal?: AbortSignal,
  ) =>
    apiClient.request<AuditTrail>({
      method: 'PATCH',
      path: `${INCIDENTS_BASE}/${encodeURIComponent(incidentId)}/status`,
      body,
      signal,
    }),

  /** EC-4: full audit trail. */
  getAuditTrail: (incidentId: string, signal?: AbortSignal) =>
    apiClient.request<AuditTrail>({
      method: 'GET',
      path: `${INCIDENTS_BASE}/${encodeURIComponent(incidentId)}/audit-trail`,
      signal,
    }),

  /** Module liveness. */
  getHealth: (signal?: AbortSignal) =>
    apiClient.request<{ status: string; module: string }>({
      method: 'GET',
      path: `${INCIDENTS_BASE}/health`,
      signal,
    }),

  // --- Badcases -----------------------------------------------------------
  /** FR-023: badcase list. */
  listBadcases: (signal?: AbortSignal) =>
    apiClient.request<BadcaseListResponse>({
      method: 'GET',
      path: BADCASES_BASE,
      signal,
    }),

  /** FR-023: single badcase detail. */
  getBadcase: (badcaseId: string, signal?: AbortSignal) =>
    apiClient.request<Badcase>({
      method: 'GET',
      path: `${BADCASES_BASE}/${encodeURIComponent(badcaseId)}`,
      signal,
    }),

  /** FR-023 + AC-23.4: escalate badcase to incident (requires BADCASE_CHANGE). */
  escalateBadcase: (badcaseId: string, signal?: AbortSignal) =>
    apiClient.request<BadcaseEscalateResponse>({
      method: 'POST',
      path: `${BADCASES_BASE}/${encodeURIComponent(badcaseId)}/escalate`,
      signal,
    }),

  /** Module liveness. */
  getBadcasesHealth: (signal?: AbortSignal) =>
    apiClient.request<{ status: string; module: string }>({
      method: 'GET',
      path: `${BADCASES_BASE}/health`,
      signal,
    }),
}

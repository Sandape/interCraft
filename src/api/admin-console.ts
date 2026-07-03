/**
 * Admin Console / Log Center API client — REQ-039 B2.
 *
 * Wraps the 7 backend endpoints plus the two new list endpoints
 * (GET /traces and GET /traces/{id}/nodes) added in B2.
 *
 * Endpoints:
 *
 * - GET    /api/v1/admin-console/observability/traces?limit=
 * - GET    /api/v1/admin-console/observability/traces/{id}/nodes
 * - GET    /api/v1/admin-console/observability/traces/{id}/nodes/{nid}/payload
 * - GET    /api/v1/admin-console/observability/tasks/{id}/tags
 * - POST   /api/v1/admin-console/observability/tasks/{id}/tags
 * - DELETE /api/v1/admin-console/observability/tasks/{id}/tags
 * - POST   /api/v1/admin-console/observability/traces/{id}/replay
 * - POST   /api/v1/admin-console/observability/traces/diff
 */
import { apiClient } from './client'
import type {
  AdminDiffRequest,
  AdminDiffResponse,
  AdminReplayResponse,
  AdminTaskTag,
  AdminTaskTagCreateRequest,
  AdminTaskTagListResponse,
  AdminTrace,
  AdminTraceListResponse,
  AdminTraceNodesResponse,
} from '../types/admin-console'

const BASE = '/api/v1/admin-console/observability'

export interface AdminTraceListParams {
  limit?: number
  task_type?: string
  status?: string
  since?: string
}

export const adminConsoleApi = {
  /** FR-001 — list the most recent traces. */
  listTraces: (params: AdminTraceListParams = {}, signal?: AbortSignal) =>
    apiClient.request<AdminTraceListResponse>({
      method: 'GET',
      path: `${BASE}/traces`,
      query: {
        limit: params.limit ?? 100,
        task_type: params.task_type || undefined,
        status: params.status || undefined,
        since: params.since || undefined,
      },
      signal,
    }),

  /** Detail panel — node tree for a single trace. */
  listTraceNodes: (traceId: string, signal?: AbortSignal) =>
    apiClient.request<AdminTraceNodesResponse>({
      method: 'GET',
      path: `${BASE}/traces/${traceId}/nodes`,
      signal,
    }),

  /** FR-025..FR-027 — byte-range slice of one node's payload. */
  fetchNodePayload: (
    traceId: string,
    nodeId: string,
    opts: { offset?: number; limit?: number; signal?: AbortSignal } = {},
  ) =>
    apiClient.request<string>({
      method: 'GET',
      path: `${BASE}/traces/${traceId}/nodes/${nodeId}/payload`,
      query: {
        offset: opts.offset ?? 0,
        limit: opts.limit ?? 51200,
      },
      signal: opts.signal,
    }),

  /** FR-017 — list the caller's tags on a task. */
  listTags: (taskId: string, signal?: AbortSignal) =>
    apiClient.request<AdminTaskTagListResponse>({
      method: 'GET',
      path: `${BASE}/tasks/${taskId}/tags`,
      signal,
    }),

  /** FR-017 — add a tag. */
  addTag: (taskId: string, body: AdminTaskTagCreateRequest) =>
    apiClient.request<AdminTaskTag>({
      method: 'POST',
      path: `${BASE}/tasks/${taskId}/tags`,
      body,
    }),

  /** FR-017 — hard-delete a tag. */
  deleteTag: (taskId: string, tag: string) =>
    apiClient.request<{ deleted: boolean; tag: string }>({
      method: 'DELETE',
      path: `${BASE}/tasks/${taskId}/tags`,
      query: { tag },
    }),

  /** FR-006..FR-008 — replay a trace (creates a new one). */
  replayTrace: (
    traceId: string,
    note?: string,
  ) =>
    apiClient.request<AdminReplayResponse>({
      method: 'POST',
      path: `${BASE}/traces/${traceId}/replay`,
      body: note ? { note } : {},
    }),

  /** FR-011..FR-014 — compute node-aligned diff. */
  diffTraces: (body: AdminDiffRequest) =>
    apiClient.request<AdminDiffResponse>({
      method: 'POST',
      path: `${BASE}/traces/diff`,
      body,
    }),
}

/**
 * Admin Console Saved Views API client — REQ-044 CROSS FR-006.
 *
 * Endpoints (mounted by backend/app/main.py at
 * `/api/v1/admin-console/saved-views`):
 *
 * - GET    /api/v1/admin-console/saved-views?workspace_id=X  — list views
 * - POST   /api/v1/admin-console/saved-views                — create view
 * - GET    /api/v1/admin-console/saved-views/{id}           — detail
 * - PATCH  /api/v1/admin-console/saved-views/{id}           — update
 * - DELETE /api/v1/admin-console/saved-views/{id}           — delete
 * - GET    /api/v1/admin-console/saved-views/health         — module liveness
 *
 * Cross-team contract lock (memory feedback_cross_team_contract_l031):
 * any change here MUST be synced with
 * backend/app/modules/admin_console/saved_views/{api,schemas,service}.py.
 */
import { apiClient } from './client'
import type {
  SavedView,
  SavedViewCreateRequest,
  SavedViewDetailResponse,
  SavedViewListResponse,
  SavedViewUpdateRequest,
  WorkspaceId,
} from '../types/admin-console'

const BASE = '/api/v1/admin-console/saved-views'

// Backend request bodies (strict trust_status) — separate from the
// frontend SavedViewCreateRequest which uses legacy trustStatus.
interface SavedViewCreateBody {
  name: string
  workspace_id: WorkspaceId
  filters: Record<string, string>
  description: string
  shared_with: string[]
  trust_status: 'verified' | 'pending' | 'deprecated'
}

export const adminSavedViewsApi = {
  /** FR-006 AC-6.1 — list saved views for a workspace. */
  list: (workspaceId: WorkspaceId, signal?: AbortSignal) =>
    apiClient.request<SavedViewListResponse>({
      method: 'GET',
      path: BASE,
      query: { workspace_id: workspaceId },
      signal,
    }),

  /** FR-006 AC-6.2 — create a saved view (POST). */
  create: (
    body: SavedViewCreateBody,
    signal?: AbortSignal,
  ) =>
    apiClient.request<SavedView>({
      method: 'POST',
      path: BASE,
      body,
      signal,
    }),

  /** FR-006 AC-6.3 — get a saved view (GET /{id}). */
  get: (savedViewId: string, signal?: AbortSignal) =>
    apiClient.request<SavedViewDetailResponse>({
      method: 'GET',
      path: `${BASE}/${savedViewId}`,
      signal,
    }),

  /** FR-006 AC-6.4 — update a saved view (PATCH). */
  update: (
    savedViewId: string,
    body: SavedViewUpdateRequest,
    signal?: AbortSignal,
  ) =>
    apiClient.request<SavedView>({
      method: 'PATCH',
      path: `${BASE}/${savedViewId}`,
      body,
      signal,
    }),

  /** FR-006 AC-6.5 — delete a saved view (DELETE). */
  delete: (savedViewId: string, signal?: AbortSignal) =>
    apiClient.request<void>({
      method: 'DELETE',
      path: `${BASE}/${savedViewId}`,
      signal,
    }),
}
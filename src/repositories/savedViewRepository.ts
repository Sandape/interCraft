/**
 * savedViewRepository — REQ-044 CROSS FR-006 real implementation.
 *
 * [CROSS-TEAM-DEBT cleared 2026-07-04] Phase 2 US-CROSS delivered
 * real persistence. The previous IA-stage stub threw
 * NotImplementedError; this rewrite hooks into the backend
 * ``/api/v1/admin-console/saved-views`` router mounted by
 * ``backend/app/main.py``.
 *
 * Iron rule A (memory req_032_v2_repo_stub_trap): no silent fallback.
 * Every method calls the real backend API via ``apiClient.request``
 * and surfaces errors verbatim. No ``Promise.resolve([])``,
 * no ``console.warn`` swallowing — a network failure throws.
 *
 * Cross-team contract (memory feedback_cross_team_contract_l031):
 * - ``SharedWithRole`` is mirrored verbatim against the backend
 *   Pydantic Literal.
 * - ``SavedViewListResponse`` envelope fields match the backend
 *   ``SavedViewListResponse``.
 */
import { apiClient } from '../api/client'
import type {
  CreateSavedViewInput,
  SavedView,
  SavedViewCreateResponse,
  SavedViewDetailResponse,
  SavedViewListResponse,
  SharedWithRole,
  UpdateSavedViewInput,
  WorkspaceId,
} from '../types/admin-console'

// Re-export for callers that still expect the legacy type names.
export type {
  CreateSavedViewInput,
  SavedView,
  SavedViewCreateResponse,
  SavedViewDetailResponse,
  SavedViewListResponse,
  UpdateSavedViewInput,
}

export const SAVED_VIEWS_BASE = '/api/v1/admin-console/saved-views'

/**
 * Map the 3-state strict backend trust_status to the legacy
 * 'trusted' / 'provisional' / 'unverified' values that some
 * legacy callers (US1 IA shell) still consume.
 */
function mapTrustStatus(
  s: 'verified' | 'pending' | 'deprecated' | undefined,
): SavedView['trustStatus'] {
  switch (s) {
    case 'verified':
      return 'trusted'
    case 'pending':
      return 'provisional'
    case 'deprecated':
      return 'unverified'
    default:
      return 'provisional'
  }
}

function reverseMapTrustStatus(
  s: SavedView['trustStatus'],
): 'verified' | 'pending' | 'deprecated' {
  switch (s) {
    case 'trusted':
      return 'verified'
    case 'provisional':
      return 'pending'
    case 'unverified':
      return 'deprecated'
    case 'verified':
      return 'verified'
    case 'pending':
      return 'pending'
    case 'deprecated':
      return 'deprecated'
  }
}

export interface SavedViewRepository {
  list(workspaceId: WorkspaceId): Promise<SavedViewListResponse>
  get(id: string): Promise<SavedViewDetailResponse>
  create(
    workspaceId: WorkspaceId,
    input: CreateSavedViewInput,
  ): Promise<SavedViewCreateResponse>
  update(id: string, input: UpdateSavedViewInput): Promise<SavedView>
  delete(id: string): Promise<void>
}

export class HttpSavedViewRepository implements SavedViewRepository {
  async list(workspaceId: WorkspaceId): Promise<SavedViewListResponse> {
    const resp = await apiClient.request<SavedViewListResponse>({
      method: 'GET',
      path: SAVED_VIEWS_BASE,
      query: { workspace_id: workspaceId },
    })
    // Map trust_status strict→legacy on every view so legacy callers
    // that read SavedView.trustStatus as 'trusted'|'provisional'|
    // 'unverified' keep working.
    return {
      ...resp,
      views: resp.views.map((v) => ({
        ...v,
        trustStatus: mapTrustStatus(v.trustStatus as never),
      })),
    }
  }

  async get(id: string): Promise<SavedViewDetailResponse> {
    const resp = await apiClient.request<SavedViewDetailResponse>({
      method: 'GET',
      path: `${SAVED_VIEWS_BASE}/${id}`,
    })
    return {
      ...resp,
      view: {
        ...resp.view,
        trustStatus: mapTrustStatus(resp.view.trustStatus as never),
      },
    }
  }

  async create(
    workspaceId: WorkspaceId,
    input: CreateSavedViewInput,
  ): Promise<SavedViewCreateResponse> {
    const resp = await apiClient.request<SavedViewCreateResponse>({
      method: 'POST',
      path: SAVED_VIEWS_BASE,
      body: {
        name: input.name,
        workspace_id: workspaceId,
        filters: input.filters,
        description: input.description,
        shared_with: [] as SharedWithRole[],
        trust_status: reverseMapTrustStatus(input.trustStatus),
      },
    })
    return {
      view: {
        ...resp.view,
        trustStatus: mapTrustStatus(resp.view.trustStatus as never),
      },
      audit_event_id: resp.audit_event_id,
    }
  }

  async update(id: string, input: UpdateSavedViewInput): Promise<SavedView> {
    const body: Record<string, unknown> = {}
    if (input.name !== undefined) body.name = input.name
    if (input.filters !== undefined) body.filters = input.filters
    if (input.description !== undefined) body.description = input.description
    if (input.trustStatus !== undefined) {
      body.trust_status = reverseMapTrustStatus(input.trustStatus)
    }
    const resp = await apiClient.request<SavedView>({
      method: 'PATCH',
      path: `${SAVED_VIEWS_BASE}/${id}`,
      body,
    })
    return {
      ...resp,
      trustStatus: mapTrustStatus(resp.trustStatus as never),
    }
  }

  async delete(id: string): Promise<void> {
    await apiClient.request<void>({
      method: 'DELETE',
      path: `${SAVED_VIEWS_BASE}/${id}`,
    })
  }
}

export const savedViewRepository: SavedViewRepository =
  new HttpSavedViewRepository()
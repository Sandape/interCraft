/**
 * React Query hooks for the Saved Views workspace (REQ-044 CROSS FR-006).
 *
 * - useSavedViews — list for a workspace (role-aware filter at backend)
 * - useSavedView — single detail
 * - useCreateSavedView — create mutation
 * - useUpdateSavedView — update mutation
 * - useDeleteSavedView — delete mutation
 *
 * Cross-team contract (memory feedback_cross_team_contract_l031):
 * any new hook MUST be wired to the backend capability tokens
 * SAVED_VIEW_VIEW (read) + SAVED_VIEW_CHANGE (write).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminSavedViewsApi } from '@/api/admin-saved-views'
import type { SavedViewUpdateRequest, WorkspaceId } from '@/types/admin-console'

// ---------------------------------------------------------------------------
// Query keys (centralized so mutations can invalidate cleanly)
// ---------------------------------------------------------------------------

export const savedViewsKeys = {
  all: ['admin-console', 'saved-views'] as const,
  list: (workspaceId: WorkspaceId) =>
    [...savedViewsKeys.all, 'list', workspaceId] as const,
  detail: (id: string) =>
    [...savedViewsKeys.all, 'detail', id] as const,
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useSavedViews(workspaceId: WorkspaceId) {
  return useQuery({
    queryKey: savedViewsKeys.list(workspaceId),
    queryFn: ({ signal }) => adminSavedViewsApi.list(workspaceId, signal),
    staleTime: 60_000,
    enabled: Boolean(workspaceId),
  })
}

export function useSavedView(savedViewId: string) {
  return useQuery({
    queryKey: savedViewsKeys.detail(savedViewId),
    queryFn: ({ signal }) => adminSavedViewsApi.get(savedViewId, signal),
    staleTime: 30_000,
    enabled: Boolean(savedViewId),
  })
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

interface CreateSavedViewBody {
  name: string
  workspace_id: WorkspaceId
  filters: Record<string, string>
  description: string
  shared_with: string[]
  trust_status: 'verified' | 'pending' | 'deprecated'
}

export function useCreateSavedView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateSavedViewBody) =>
      adminSavedViewsApi.create(body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({
        queryKey: savedViewsKeys.list(vars.workspace_id),
      })
    },
  })
}

interface UpdateSavedViewArgs {
  savedViewId: string
  workspaceId: WorkspaceId
  body: SavedViewUpdateRequest
}

export function useUpdateSavedView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ savedViewId, body }: UpdateSavedViewArgs) =>
      adminSavedViewsApi.update(savedViewId, body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({
        queryKey: savedViewsKeys.list(vars.workspaceId),
      })
      qc.invalidateQueries({
        queryKey: savedViewsKeys.detail(vars.savedViewId),
      })
    },
  })
}

export function useDeleteSavedView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ savedViewId }: { savedViewId: string; workspaceId: WorkspaceId }) =>
      adminSavedViewsApi.delete(savedViewId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({
        queryKey: savedViewsKeys.list(vars.workspaceId),
      })
    },
  })
}
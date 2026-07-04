/**
 * React Query hooks for the governance workspace (REQ-044 US6).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminGovernanceApi } from '@/api/admin-governance'
import type {
  AuditAction,
  ExportRequestCreate,
  RetentionPolicyUpdate,
  RevealRequestCreate,
} from '@/types/admin-governance'

// ---------------------------------------------------------------------------
// Query keys (centralized so mutations can invalidate cleanly)
// ---------------------------------------------------------------------------

export const governanceKeys = {
  all: ['admin-console', 'governance'] as const,
  accessMatrix: () => [...governanceKeys.all, 'access-matrix'] as const,
  audit: (filters: { actor?: string; action?: AuditAction } = {}) =>
    [...governanceKeys.all, 'audit', filters] as const,
  revealRequests: () => [...governanceKeys.all, 'reveal-requests'] as const,
  retentionPolicy: () => [...governanceKeys.all, 'retention-policy'] as const,
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useAccessMatrix() {
  return useQuery({
    queryKey: governanceKeys.accessMatrix(),
    queryFn: ({ signal }) => adminGovernanceApi.getAccessMatrix(signal),
    staleTime: 60_000,
  })
}

export function useAuditEvents(
  filters: { actor?: string; action?: AuditAction } = {},
) {
  return useQuery({
    queryKey: governanceKeys.audit(filters),
    queryFn: ({ signal }) => adminGovernanceApi.listAuditEvents(filters, signal),
    staleTime: 30_000,
  })
}

export function useRevealRequests() {
  return useQuery({
    queryKey: governanceKeys.revealRequests(),
    queryFn: ({ signal }) => adminGovernanceApi.listRevealRequests(signal),
    staleTime: 60_000,
  })
}

export function useRetentionPolicy() {
  return useQuery({
    queryKey: governanceKeys.retentionPolicy(),
    queryFn: ({ signal }) => adminGovernanceApi.listRetentionPolicy(signal),
    staleTime: 60_000,
  })
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateRevealRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RevealRequestCreate) =>
      adminGovernanceApi.createRevealRequest(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: governanceKeys.revealRequests() })
      qc.invalidateQueries({ queryKey: governanceKeys.audit() })
    },
  })
}

export function useCreateExport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ExportRequestCreate) =>
      adminGovernanceApi.createExport(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: governanceKeys.audit() })
    },
  })
}

export function useUpdateRetentionPolicy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RetentionPolicyUpdate) =>
      adminGovernanceApi.updateRetentionPolicy(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: governanceKeys.retentionPolicy() })
      qc.invalidateQueries({ queryKey: governanceKeys.audit() })
    },
  })
}

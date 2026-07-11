/**
 * React Query hooks for the incidents workspace (REQ-044 US4 / REQ-061 US10).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminIncidentsApi } from '@/api/admin-incidents'
import {
  productionBadcasesApi,
  type BadcaseListFilters,
} from '@/admin/api/badcases-production'
import type {
  CommentCreateRequest,
  StatusChangeRequest,
} from '@/types/admin-incidents'

export const incidentKeys = {
  all: ['admin-console', 'incidents'] as const,
  list: () => [...incidentKeys.all, 'list'] as const,
  detail: (id: string) => [...incidentKeys.all, 'detail', id] as const,
  evidence: (id: string) => [...incidentKeys.all, 'evidence', id] as const,
  comments: (id: string) => [...incidentKeys.all, 'comments', id] as const,
  auditTrail: (id: string) => [...incidentKeys.all, 'audit-trail', id] as const,
}

export const badcaseKeys = {
  all: ['admin-console', 'badcases'] as const,
  list: () => [...badcaseKeys.all, 'list'] as const,
  productionList: (filters: BadcaseListFilters = {}) =>
    [...badcaseKeys.all, 'production-list', filters] as const,
  detail: (id: string) => [...badcaseKeys.all, 'detail', id] as const,
}

export function useIncidents() {
  return useQuery({
    queryKey: incidentKeys.list(),
    queryFn: ({ signal }) => adminIncidentsApi.listIncidents(signal),
    staleTime: 60_000,
  })
}

export function useIncident(incidentId: string | null) {
  return useQuery({
    queryKey: incidentId ? incidentKeys.detail(incidentId) : ['noop'],
    queryFn: ({ signal }) =>
      adminIncidentsApi.getIncident(incidentId as string, signal),
    enabled: Boolean(incidentId),
    staleTime: 60_000,
  })
}

export function useIncidentEvidence(incidentId: string | null) {
  return useQuery({
    queryKey: incidentId ? incidentKeys.evidence(incidentId) : ['noop'],
    queryFn: ({ signal }) =>
      adminIncidentsApi.getEvidence(incidentId as string, signal),
    enabled: Boolean(incidentId),
    staleTime: 60_000,
  })
}

export function useIncidentComments(incidentId: string | null) {
  return useQuery({
    queryKey: incidentId ? incidentKeys.comments(incidentId) : ['noop'],
    queryFn: ({ signal }) =>
      adminIncidentsApi.listComments(incidentId as string, signal),
    enabled: Boolean(incidentId),
    staleTime: 30_000,
  })
}

export function useIncidentAuditTrail(incidentId: string | null) {
  return useQuery({
    queryKey: incidentId ? incidentKeys.auditTrail(incidentId) : ['noop'],
    queryFn: ({ signal }) =>
      adminIncidentsApi.getAuditTrail(incidentId as string, signal),
    enabled: Boolean(incidentId),
    staleTime: 30_000,
  })
}

export function useAddIncidentComment(incidentId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CommentCreateRequest) =>
      adminIncidentsApi.addComment(incidentId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: incidentKeys.comments(incidentId) })
    },
  })
}

export function useChangeIncidentStatus(incidentId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: StatusChangeRequest) =>
      adminIncidentsApi.changeStatus(incidentId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: incidentKeys.detail(incidentId) })
      void qc.invalidateQueries({ queryKey: incidentKeys.auditTrail(incidentId) })
      void qc.invalidateQueries({ queryKey: incidentKeys.list() })
    },
  })
}

export function useBadcases() {
  return useQuery({
    queryKey: badcaseKeys.list(),
    queryFn: ({ signal }) => adminIncidentsApi.listBadcases(signal),
    staleTime: 60_000,
  })
}

/** REQ-061 US10 canonical persistent Bad Case list. */
export function useProductionBadcases(filters: BadcaseListFilters = {}) {
  return useQuery({
    queryKey: badcaseKeys.productionList(filters),
    queryFn: ({ signal }) => productionBadcasesApi.list(filters, signal),
    staleTime: 30_000,
    retry: 1,
  })
}

export function useBadcase(badcaseId: string | null) {
  return useQuery({
    queryKey: badcaseId ? badcaseKeys.detail(badcaseId) : ['noop'],
    queryFn: ({ signal }) =>
      adminIncidentsApi.getBadcase(badcaseId as string, signal),
    enabled: Boolean(badcaseId),
    staleTime: 60_000,
  })
}

export function useEscalateBadcase() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (badcaseId: string) =>
      adminIncidentsApi.escalateBadcase(badcaseId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: badcaseKeys.list() })
      void qc.invalidateQueries({ queryKey: badcaseKeys.all })
    },
  })
}

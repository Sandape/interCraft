/** React Query hooks for ability profile dashboard. */
import { useQuery } from '@tanstack/react-query'
import { fetchDashboard, listShareLinks, listExports, getSharedProfile, getExportStatus, fetchAdminDashboard } from '@/api/abilityProfileClient'

export function useAbilityDashboard() {
  return useQuery({
    queryKey: ['abilityDashboard'],
    queryFn: fetchDashboard,
    staleTime: 30_000,
  })
}

export function useShareLinks() {
  return useQuery({
    queryKey: ['shareLinks'],
    queryFn: listShareLinks,
    staleTime: 10_000,
  })
}

export function useSharedProfile(token: string, pin?: string) {
  return useQuery({
    queryKey: ['sharedProfile', token, pin],
    queryFn: () => getSharedProfile(token, pin),
    enabled: !!token,
    staleTime: 60_000,
  })
}

export function useExportList(limit = 10) {
  return useQuery({
    queryKey: ['exportList', limit],
    queryFn: () => listExports(limit),
    staleTime: 10_000,
  })
}

export function useExportStatus(exportId: string | null) {
  return useQuery({
    queryKey: ['exportStatus', exportId],
    queryFn: () => getExportStatus(exportId!),
    enabled: !!exportId,
    refetchInterval: (query) => {
      const status = query.state.data?.data?.status
      if (status === 'completed' || status === 'failed') return false
      return 2000
    },
  })
}

export function useAdminDashboard(targetUserId: string) {
  return useQuery({
    queryKey: ['adminDashboard', targetUserId],
    queryFn: () => fetchAdminDashboard(targetUserId),
    enabled: !!targetUserId,
    staleTime: 30_000,
  })
}

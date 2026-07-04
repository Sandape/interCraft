/**
 * React Query hook for privacy-safe user lookup — REQ-044 US2 / FR-015.
 */
import { useQuery } from '@tanstack/react-query'
import { adminUsersApi } from '@/api/admin-users'

export const userSafeQueryKey = (userId: string) =>
  ['admin-users', 'safe', userId] as const

export function useUserSafe(userId: string | null | undefined) {
  return useQuery({
    queryKey: userSafeQueryKey(userId ?? '__none__'),
    queryFn: ({ signal }) => {
      if (!userId) {
        return Promise.reject(new Error('userId is required'))
      }
      return adminUsersApi.getUserSafe(userId, signal)
    },
    enabled: Boolean(userId),
    staleTime: 60_000,
    retry: false,
  })
}
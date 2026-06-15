/**
 * useCurrentUser — query the authenticated user.
 * Loads on app boot to seed `useAuthStore`.
 */
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { getAccountRepository } from '../../repositories/types'
import { useAuthStore } from '../../stores/useAuthStore'

export const CURRENT_USER_KEY = ['auth', 'me'] as const

export function useCurrentUser() {
  const setUser = useAuthStore((s) => s.setUser)
  const setStatus = useAuthStore((s) => s.setStatus)
  const query = useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: () => getAccountRepository().getMe(),
    staleTime: 60_000,
    retry: false,
  })

  useEffect(() => {
    if (query.data) {
      setUser(query.data)
    }
    if (query.isError) {
      setUser(null)
    } else if (query.isFetching) {
      setStatus('unknown')
    } else if (query.data) {
      setStatus('authenticated')
    }
  }, [query.data, query.isError, query.isFetching, setUser, setStatus])

  return query
}

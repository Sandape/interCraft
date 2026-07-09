/**
 * useCurrentUser — query the authenticated user.
 * Loads on app boot to seed `useAuthStore`.
 *
 * FR-007: Heartbeat — refetches silently when page is visible and the
 * last successful fetch is older than half the access_token TTL (7.5 min).
 * This triggers the silent-refresh chain in apiClient before the token
 * actually expires, preventing mid-session token expiry from causing a 401.
 */
import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { getAccountRepository } from '../../repositories/authRepositories'
import { useAuthStore } from '../../stores/useAuthStore'
import { hasTokens } from '../../api/token-storage'

export const CURRENT_USER_KEY = ['auth', 'me'] as const

/** Half of access_token TTL (900s / 2 = 450 000 ms) — heartbeat threshold. */
const HEARTBEAT_INTERVAL_MS = 450_000

export function useCurrentUser() {
  const setUser = useAuthStore((s) => s.setUser)
  const setStatus = useAuthStore((s) => s.setStatus)
  const query = useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: () => getAccountRepository().getMe(),
    staleTime: 60_000,
    // FR-006: retry twice with exponential backoff. The first failure may be
    // transient (apiClient's internal silent-refresh handles it); if the retry
    // still fails, fail definitively and redirect to /login.
    // apiClient 内部已有 silent-refresh retry（401 → POST /auth/refresh →
    // 重放原请求）。React Query 层面再 retry 只会让用户多等 1-3s 才看到
    // 登录页（retry: 0 避免此延迟）。
    retry: 0,
    // 无 token 时不查询（避免对未认证用户发多余的 401 请求）。
    enabled: hasTokens(),
    refetchInterval: (query) => {
      // FR-007: only heartbeat when page is visible and we have data
      // (meaning the user is authenticated).
      if (typeof document !== 'undefined' && document.visibilityState === 'visible' && query.state.data) {
        return HEARTBEAT_INTERVAL_MS
      }
      return false
    },
  })

  useEffect(() => {
    if (query.data) {
      setUser(query.data)
    }
    if (query.isError) {
      setUser(null)
      // FR-004: if the error is a session eviction, show the Toast without
      // immediately clearing tokens or redirecting.
      if (query.error && typeof query.error === 'object' && 'code' in query.error) {
        const code = (query.error as { code: string }).code
        if (code === 'auth.session_evicted') {
          useAuthStore.getState().setEvicted(true)
        }
      }
    } else if (query.isFetching) {
      setStatus('unknown')
    } else if (query.data) {
      setStatus('authenticated')
    }
  }, [query.data, query.error, query.isError, query.isFetching, setUser, setStatus])

  return query
}

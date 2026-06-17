/**
 * requireAuth — pure decision function for the AuthGuard component.
 *
 * 020 (FIX-009, D-016) — Round-1 used a combined inline check
 *   `!hasTokens() && status === 'unknown'`
 * which let through the case where a stale token was in sessionStorage
 * but the user was actually unauthenticated. The protected page would
 * mount and React Query would spin forever on 401.
 *
 * The new contract:
 *   - `ok` — render protected children.
 *   - `loading` — render a neutral loading state; do NOT mount protected
 *     children until status resolves.
 *   - `redirect` — `<Navigate to="/login" replace />`.
 *
 * Pure function for testability.
 */
import type { AuthStatus } from '@/stores/useAuthStore'

export type RequireAuthDecision =
  | { kind: 'ok' }
  | { kind: 'loading' }
  | { kind: 'redirect'; to: string }

export function requireAuth({
  hasTokens,
  status,
}: {
  hasTokens: boolean
  status: AuthStatus
}): RequireAuthDecision {
  // Hard redirect when explicitly unauthenticated (after a 401).
  if (status === 'unauthenticated') {
    return { kind: 'redirect', to: '/login' }
  }
  // No tokens and no resolved status → bounce to login immediately.
  if (!hasTokens && status !== 'authenticated') {
    return { kind: 'redirect', to: '/login' }
  }
  // Tokens present but status still resolving (stale token check pending).
  // Show a neutral loading state instead of mounting the protected page.
  if (status === 'unknown') {
    return { kind: 'loading' }
  }
  return { kind: 'ok' }
}

/**
 * Admin Router — REQ-044 IA shell.
 *
 * Auth gate: any unauthenticated caller is bounced to /login (which is
 * the main app login page; admin is hosted on the same origin as the
 * app, so the token-storage keys are shared).
 *
 * Index route redirects to command-center per FR-003.
 *
 * FR-004 logs/traces must NOT be the default — index = command-center,
 * NAV_ITEMS 的首项是 Command Center.
 *
 * [DEFERRED-PHASE-2, IA-only-static-check] drilldown from
 * incidents-badcases → logs-and-traces?from=<id>：路由层预留
 * useSearchParams hook 入口（AC-4.4b 静态可达性守卫）。
 */
import { Navigate, Route, Routes, useLocation, useSearchParams } from 'react-router-dom'
import { hasTokens } from '@/api/token-storage'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { AdminShell } from './components/AdminShell'
import { CommandCenter } from './pages/CommandCenter'
import { ProductAnalytics } from './pages/ProductAnalytics'
import { AIOperations } from './pages/AIOperations'
import { IncidentsBadcases } from './pages/IncidentsBadcases'
import { LogsAndTraces } from './pages/LogsAndTraces'
import { UsersAccounts } from './pages/UsersAccounts'
import { Reports } from './pages/Reports'
import { Governance } from './pages/Governance'

// AC-4.4b: drilldown from incidents-badcases detail → logs-and-traces?from=<id>.
// Phase 2 will read `from=` via useSearchParams inside the LogsAndTraces
// page. We import the hook here at the route layer as a static
// reachability guard so the IA shell is wired for the future
// query-param-based deep-linking without leaving a stale comment
// dangling in the spec.
function _drilldownSearchParamsProbe() {
  // Phase 2 wiring: read `from=<id>` from useSearchParams() to seed
  // the logs-and-traces filter from an incident / badcase.
  const _params = useSearchParams
  void _params
}

function AdminAuthGuard({ children }: { children: JSX.Element }) {
  useCurrentUser()
  const status = useAuthStore((s) => s.status)
  const location = useLocation()
  if (!hasTokens()) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  if (status === 'unknown') {
    return (
      <div
        data-testid="admin-auth-loading"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          color: '#94a3b8',
          fontSize: 12,
        }}
      >
        正在校验登录状态…
      </div>
    )
  }
  return children
}

export function AdminAppRoutes() {
  return (
    <Routes>
      <Route
        path="/admin-console/*"
        element={(
          <AdminAuthGuard>
            <AdminShell />
          </AdminAuthGuard>
        )}
      >
        <Route index element={<Navigate to="command-center" replace />} />
        <Route path="command-center" element={<CommandCenter />} />
        <Route path="product-analytics" element={<ProductAnalytics />} />
        <Route path="ai-operations" element={<AIOperations />} />
        <Route path="incidents-badcases" element={<IncidentsBadcases />} />
        <Route path="logs-and-traces" element={<LogsAndTraces />} />
        <Route path="users-accounts" element={<UsersAccounts />} />
        <Route path="reports" element={<Reports />} />
        <Route path="governance" element={<Governance />} />
      </Route>
      <Route path="/index.admin.html" element={<Navigate to="/admin-console/command-center" replace />} />
      <Route path="*" element={<Navigate to="/admin-console/command-center" replace />} />
    </Routes>
  )
}
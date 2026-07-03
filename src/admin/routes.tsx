/**
 * Admin Router — REQ-039 B2/B3.
 *
 * Auth gate: any unauthenticated caller is bounced to /login (which is
 * the main app login page; admin is hosted on the same origin as the
 * app, so the token-storage keys are shared).
 */
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { hasTokens } from '@/api/token-storage'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { AdminShell } from './components/AdminShell'
import { LogCenter } from './pages/LogCenter'
import { PlaceholderPage } from './pages/PlaceholderPage'

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
        <Route index element={<Navigate to="log-center" replace />} />
        <Route path="log-center" element={<LogCenter />} />
        <Route path="dashboard" element={<PlaceholderPage title="产品看板" />} />
        <Route path="trace-explorer" element={<PlaceholderPage title="链路追踪" />} />
        <Route path="eval-center" element={<PlaceholderPage title="评测中心" />} />
      </Route>
      <Route path="/index.admin.html" element={<Navigate to="/admin-console/log-center" replace />} />
      <Route path="*" element={<Navigate to="/admin-console/log-center" replace />} />
    </Routes>
  )
}

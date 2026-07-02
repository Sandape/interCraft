/**
 * Admin Router — REQ-039 B2.
 *
 * Wraps the route config in <Routes>. Auth gate: any unauthenticated
 * caller is bounced to /login (which is the main app login page; admin
 * is hosted on the same origin as the app, so the token-storage keys
 * are shared).
 */
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { hasTokens } from '@/api/token-storage'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { ADMIN_ROUTE_CONFIG } from './components/AdminShell'

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
      {ADMIN_ROUTE_CONFIG.map((route) => (
        <Route key={route.path} path={route.path} element={<AdminAuthGuard>{route.element}</AdminAuthGuard>}>
          {route.children?.map((child) => (
            <Route
              key={child.path ?? 'index'}
              index={child.index ?? false}
              path={child.path}
              element={child.element}
            />
          ))}
        </Route>
      ))}
      <Route path="*" element={<Navigate to="/admin-console/log-center" replace />} />
    </Routes>
  )
}

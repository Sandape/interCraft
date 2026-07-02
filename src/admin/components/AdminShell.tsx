/**
 * AdminShell — REQ-039 B2.
 *
 * The 4-item sidebar (产品看板 / 日志中心 / 链路追踪 / 评测中心) is the
 * primary navigation surface inside the admin console. Log center is
 * the only fully-implemented page in B2; the other three show "敬请期待"
 * placeholders so the menu is browsable.
 *
 * Topbar shows the current user + role badge. We use `useCurrentUser`
 * from the existing app because the auth/access-token plumbing is
 * already wired in `src/api/token-storage.ts`.
 */
import { NavLink, Outlet, useLocation, Navigate } from 'react-router-dom'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { useAuthStore } from '@/stores/useAuthStore'
import { LogCenter } from '@/admin/pages/LogCenter'
import { PlaceholderPage } from '@/admin/pages/PlaceholderPage'

interface NavItem {
  to: string
  label: string
  implemented: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/admin-console/dashboard', label: '产品看板', implemented: false },
  { to: '/admin-console/log-center', label: '日志中心', implemented: true },
  { to: '/admin-console/trace-explorer', label: '链路追踪', implemented: false },
  { to: '/admin-console/eval-center', label: '评测中心', implemented: false },
]

function currentTitle(pathname: string): string {
  const match = NAV_ITEMS.find((item) => item.to === pathname)
  if (match) return match.label
  if (pathname.startsWith('/admin-console/log-center')) return '日志中心'
  return 'Admin Console'
}

export function AdminShell() {
  useCurrentUser()
  const user = useAuthStore((s) => s.user)
  const location = useLocation()
  // Treat demo user as admin unconditionally per AC matrix IC-6; the
  // server is the source of truth for capability checks, but the UI
  // hides affordances it can't use.
  const isAdmin = Boolean(user)

  return (
    <div className="ac-shell">
      <aside className="ac-shell__sidebar">
        <div className="ac-shell__brand">
          <span className="ac-shell__brand-mark" />
          <span>Admin Console</span>
        </div>
        <nav className="ac-shell__nav" aria-label="admin-section">
          <div className="ac-shell__nav-label">运营</div>
          {NAV_ITEMS.map((item) =>
            item.implemented ? (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive
                    ? 'ac-shell__nav-item ac-shell__nav-item--active'
                    : 'ac-shell__nav-item'
                }
              >
                {item.label}
              </NavLink>
            ) : (
              <span
                key={item.to}
                className="ac-shell__nav-item ac-shell__nav-item--disabled"
                title="敬请期待"
              >
                {item.label}
                <span
                  style={{
                    marginLeft: 'auto',
                    fontSize: 10,
                    color: 'var(--ac-ink-faint)',
                  }}
                >
                  敬请期待
                </span>
              </span>
            ),
          )}
        </nav>
      </aside>

      <header className="ac-shell__topbar">
        <div className="ac-shell__topbar-title">
          InterCraft · {currentTitle(location.pathname)}
        </div>
        <div className="ac-shell__topbar-user">
          {user?.email ?? 'unknown'}
          <span className="ac-shell__topbar-role">
            {isAdmin ? 'admin' : 'viewer'}
          </span>
        </div>
      </header>

      <main className="ac-shell__main">
        <Outlet />
      </main>
    </div>
  )
}

export const ADMIN_ROUTE_CONFIG = [
  {
    path: '/admin-console',
    element: <AdminShell />,
    children: [
      { index: true, element: <Navigate to="/admin-console/log-center" replace /> },
      { path: 'log-center', element: <LogCenter /> },
      { path: 'dashboard', element: <PlaceholderPage title="产品看板" /> },
      { path: 'trace-explorer', element: <PlaceholderPage title="链路追踪" /> },
      { path: 'eval-center', element: <PlaceholderPage title="评测中心" /> },
    ],
  },
]

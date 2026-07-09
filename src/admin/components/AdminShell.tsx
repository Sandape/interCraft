/**
 * AdminShell — REQ-051 simplified admin console shell.
 *
 * All 8 workspaces are visible to admin users. The old 6-role
 * capability matrix has been replaced with a single ``is_admin``
 * boolean check. The RoleBadgeDropdown and resolveRole/roleToWorkspaces
 * functions have been removed.
 */
import { NavLink, useLocation, Navigate, Link } from 'react-router-dom'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { useAuthStore } from '@/stores/useAuthStore'
import type { WorkspaceId } from '@/types/admin-console'
import { CommandCenter } from '@/admin/pages/CommandCenter'
import { ProductAnalytics } from '@/admin/pages/ProductAnalytics'
import { AIOperations } from '@/admin/pages/AIOperations'
import { IncidentsBadcases } from '@/admin/pages/IncidentsBadcases'
import { LogsAndTraces } from '@/admin/pages/LogsAndTraces'
import { UsersAccounts } from '@/admin/pages/UsersAccounts'
import { Reports } from '@/admin/pages/Reports'
import { Governance } from '@/admin/pages/Governance'

interface NavItem {
  to: string
  label: string
  workspace: WorkspaceId
}

const NAV_ITEMS: NavItem[] = [
  { to: '/admin-console/command-center', label: '指挥中心', workspace: 'command-center' },
  { to: '/admin-console/product-analytics', label: '产品分析', workspace: 'product-analytics' },
  { to: '/admin-console/ai-operations', label: 'AI 运营', workspace: 'ai-operations' },
  { to: '/admin-console/incidents-badcases', label: '事件与差例', workspace: 'incidents-badcases' },
  { to: '/admin-console/logs-and-traces', label: '日志与链路', workspace: 'logs-and-traces' },
  { to: '/admin-console/users-accounts', label: '用户与账户', workspace: 'users-accounts' },
  { to: '/admin-console/reports', label: '报告中心', workspace: 'reports' },
  { to: '/admin-console/governance', label: '治理与审计', workspace: 'governance' },
]

function currentTitle(pathname: string): string {
  const match = NAV_ITEMS.find((item) => item.to === pathname)
  if (match) return match.label
  if (pathname.startsWith('/admin-console/logs-and-traces')) return '日志与链路'
  if (pathname.startsWith('/admin-console/command-center')) return '指挥中心'
  return '管理后台'
}

export function AdminShell() {
  useCurrentUser()
  const user = useAuthStore((s) => s.user)
  const location = useLocation()
  const isAdmin = Boolean(user?.is_admin)

  // REQ-051: admin users see all 8 workspaces.
  const visibleItems = isAdmin ? NAV_ITEMS : []

  return (
    <div className="ac-shell">
      <aside className="ac-shell__sidebar">
        <div className="ac-shell__brand">
          <span className="ac-shell__brand-mark" />
          <span>管理后台</span>
        </div>
        <nav className="ac-shell__nav" aria-label="admin-section">
          <div className="ac-shell__nav-label">运营</div>
          {visibleItems.map((item) => (
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
          ))}
        </nav>
      </aside>

      <header className="ac-shell__topbar">
        <div className="ac-shell__topbar-title">
          <Link to="/dashboard" style={{ color: 'inherit', textDecoration: 'none' }}>
            InterCraft
          </Link>
          {' · '}
          {currentTitle(location.pathname)}
        </div>
        <div className="ac-shell__topbar-user">
          {user?.email ?? 'unknown'}
        </div>
      </header>

      <main className="ac-shell__main">
        {(() => {
          const p = location.pathname;
          if (p.startsWith('/admin-console/command-center')) return <CommandCenter />;
          if (p.startsWith('/admin-console/product-analytics')) return <ProductAnalytics />;
          if (p.startsWith('/admin-console/ai-operations')) return <AIOperations />;
          if (p.startsWith('/admin-console/incidents-badcases')) return <IncidentsBadcases />;
          if (p.startsWith('/admin-console/logs-and-traces')) return <LogsAndTraces />;
          if (p.startsWith('/admin-console/users-accounts')) return <UsersAccounts />;
          if (p.startsWith('/admin-console/reports')) return <Reports />;
          if (p.startsWith('/admin-console/governance')) return <Governance />;
          return <Navigate to="/admin-console/command-center" replace />;
        })()}
      </main>
    </div>
  )
}

export const ADMIN_ROUTE_CONFIG = [
  {
    path: '/admin-console/*',
    element: <AdminShell />,
    children: [
      { index: true, element: <Navigate to="/admin-console/command-center" replace /> },
      { path: 'command-center', element: <CommandCenter /> },
      { path: 'product-analytics', element: <ProductAnalytics /> },
      { path: 'ai-operations', element: <AIOperations /> },
      { path: 'incidents-badcases', element: <IncidentsBadcases /> },
      { path: 'logs-and-traces', element: <LogsAndTraces /> },
      { path: 'users-accounts', element: <UsersAccounts /> },
      { path: 'reports', element: <Reports /> },
      { path: 'governance', element: <Governance /> },
    ],
  },
]
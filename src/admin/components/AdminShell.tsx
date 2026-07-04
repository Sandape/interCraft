/**
 * AdminShell — REQ-044 IA shell + CROSS FR-006 / FR-002 role-aware
 * top-bar integration.
 *
 * The legacy 4-item sidebar is gone. The new top-level IA exposes 8
 * stable workspaces
 * (command-center / product-analytics / ai-operations / incidents-badcases
 * / logs-and-traces / users-accounts / reports / governance), filtered
 * through `roleToWorkspaces(role)` per spec FR-002.
 *
 * IA 阶段（Phase 1）role 的解析来源:
 *   1. `localStorage.auth-user.role` （Playwright EC-3b weird-role 注入通道）
 *   2. `useAuthStore.user.email === 'demo@intercraft.io'` → PM 硬编码兜底
 *   3. `useAuthStore.user.role` （后端真 RBAC 上线后由 Phase 2 US6 同步）
 *   4. fallback → 'pm' （command-center 单项可见）
 *
 * CROSS FR-002 / AC-2.4: the top-bar role badge is now a clickable
 * dropdown (``<RoleBadgeDropdown/>``) for dev/test role switching
 * — the resolver still reads localStorage first so external
 * Playwright tests continue to drive the role via ``auth-user``.
 *
 * [CROSS-TEAM-DEBT] 后端 `WorkspaceId` / `ConsoleRole` Pydantic Literal
 * 与本前端 union 字面同步在 Phase 2 US6 落地。
 */
import { NavLink, Outlet, useLocation, Navigate } from 'react-router-dom'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { useAuthStore } from '@/stores/useAuthStore'
import type { ConsoleRole, WorkspaceId } from '@/types/admin-console'
import { CommandCenter } from '@/admin/pages/CommandCenter'
import { ProductAnalytics } from '@/admin/pages/ProductAnalytics'
import { AIOperations } from '@/admin/pages/AIOperations'
import { IncidentsBadcases } from '@/admin/pages/IncidentsBadcases'
import { LogsAndTraces } from '@/admin/pages/LogsAndTraces'
import { UsersAccounts } from '@/admin/pages/UsersAccounts'
import { Reports } from '@/admin/pages/Reports'
import { Governance } from '@/admin/pages/Governance'
import { RoleBadgeDropdown } from './RoleBadgeDropdown'

interface NavItem {
  to: string
  label: string
  workspace: WorkspaceId
}

// NOTE: command-center is first by FR-004 — logs/traces must not be the
// default PM experience. EC-3 (weird role) → roleToWorkspaces falls back
// to ['command-center'] so this same `NAV_ITEMS` is filtered to a single
// entry, and the spec asserts the first visible item is Command Center.
const NAV_ITEMS: NavItem[] = [
  { to: '/admin-console/command-center', label: 'Command Center', workspace: 'command-center' },
  { to: '/admin-console/product-analytics', label: 'Product Analytics', workspace: 'product-analytics' },
  { to: '/admin-console/ai-operations', label: 'AI Operations', workspace: 'ai-operations' },
  { to: '/admin-console/incidents-badcases', label: 'Incidents & Badcases', workspace: 'incidents-badcases' },
  { to: '/admin-console/logs-and-traces', label: 'Logs & Traces', workspace: 'logs-and-traces' },
  { to: '/admin-console/users-accounts', label: 'Users & Accounts', workspace: 'users-accounts' },
  { to: '/admin-console/reports', label: 'Reports', workspace: 'reports' },
  { to: '/admin-console/governance', label: 'Governance', workspace: 'governance' },
]

// FR-002 角色 → workspace 可见性矩阵.
// 'unknown' role / 任何不在 5 角色 union 内的字符串 → fallback command-center
// (EC-3 / EC-3b: weird-role Playwright 实证).
function roleToWorkspaces(role: ConsoleRole): WorkspaceId[] {
  switch (role) {
    case 'pm':
      return [
        'command-center',
        'product-analytics',
        'ai-operations',
        'incidents-badcases',
        'logs-and-traces',
        'reports',
      ]
    case 'operations':
      return [
        'command-center',
        'product-analytics',
        'incidents-badcases',
        'logs-and-traces',
        'users-accounts',
      ]
    case 'maintainer':
      return [
        'command-center',
        'ai-operations',
        'incidents-badcases',
        'logs-and-traces',
        'users-accounts',
        'reports',
      ]
    case 'reviewer':
      return [
        'command-center',
        'product-analytics',
        'ai-operations',
        'reports',
      ]
    case 'owner':
      return [
        'command-center',
        'product-analytics',
        'ai-operations',
        'incidents-badcases',
        'logs-and-traces',
        'users-accounts',
        'reports',
        'governance',
      ]
    case 'unknown':
    default:
      // EC-3 / EC-3b fallback: weird role → PM (command-center single visible).
      return ['command-center']
  }
}

function currentTitle(pathname: string): string {
  const match = NAV_ITEMS.find((item) => item.to === pathname)
  if (match) return match.label
  if (pathname.startsWith('/admin-console/logs-and-traces')) return 'Logs & Traces'
  if (pathname.startsWith('/admin-console/command-center')) return 'Command Center'
  return 'Admin Console'
}

// IA 阶段 role 解析：localStorage.auth-user.role > demo@intercraft.io fallback > useAuthStore.user.role > 'unknown'
function resolveRole(): ConsoleRole {
  let candidate: string | undefined
  if (typeof window !== 'undefined') {
    try {
      const raw = window.localStorage.getItem('auth-user')
      if (raw) {
        const parsed = JSON.parse(raw) as { role?: string }
        if (parsed?.role) candidate = parsed.role
      }
    } catch {
      /* ignore — localStorage may be unavailable */
    }
  }
  // demo@intercraft.io → PM 硬编码兜底（IA 阶段可接受 fallback，等后端 RBAC 上线替换）
  // note: the localStorage role, when present, wins so Playwright EC-3b can override.
  if (!candidate) {
    const storeUser = useAuthStore.getState().user
    if (storeUser?.email === 'demo@intercraft.io') {
      candidate = 'pm'
    } else if (storeUser && (storeUser as { role?: string }).role) {
      candidate = (storeUser as { role?: string }).role
    }
  }
  const valid: ConsoleRole[] = ['pm', 'operations', 'maintainer', 'reviewer', 'owner']
  if (candidate && (valid as string[]).includes(candidate)) {
    return candidate as ConsoleRole
  }
  // unknown / weird role → fallback 'unknown' (roleToWorkspaces returns ['command-center'])
  return 'unknown'
}

export function AdminShell() {
  useCurrentUser()
  const user = useAuthStore((s) => s.user)
  const location = useLocation()
  // Treat demo user as admin unconditionally per AC matrix IC-6; the
  // server is the source of truth for capability checks, but the UI
  // hides affordances it can't use.
  const isAdmin = Boolean(user)

  // EC-4 fallback: role 解析失败 (network error / 5xx) → 静默降级 command-center 单项
  let role: ConsoleRole = 'unknown'
  let visibleWorkspaces: WorkspaceId[] = ['command-center']
  try {
    role = resolveRole()
    visibleWorkspaces = roleToWorkspaces(role)
  } catch (err) {
    if (typeof console !== 'undefined') {
      console.error('AdminShell role resolve failed:', err)
    }
  }

  const visibleItems = NAV_ITEMS.filter((item) => visibleWorkspaces.includes(item.workspace))

  return (
    <div className="ac-shell">
      <aside className="ac-shell__sidebar">
        <div className="ac-shell__brand">
          <span className="ac-shell__brand-mark" />
          <span>Admin Console</span>
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
          InterCraft · {currentTitle(location.pathname)}
        </div>
        <div className="ac-shell__topbar-user">
          {user?.email ?? 'unknown'}
          <RoleBadgeDropdown role={isAdmin ? role : 'unknown'} />
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
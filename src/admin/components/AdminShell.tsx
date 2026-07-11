/**
 * AdminShell — REQ-051 + REQ-061 T165 capability-aware navigation.
 *
 * Named AI admin capabilities gate workspace visibility. Four inspection
 * routes (ai-operations / incidents-badcases / logs-and-traces / governance)
 * remain stable. Non-admin users still see an empty nav.
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
import { AIReleaseGovernance } from '@/admin/pages/AIReleaseGovernance'
import { ModelPolicies } from '@/admin/pages/ModelPolicies'

/** Named capabilities used for soft nav gating (REQ-061). */
export const AI_ADMIN_CAPABILITIES = {
  SUPPORT_READ: 'ai.support.read',
  OPERATIONS_READ: 'ai.operations.read',
  QUALITY_BADCASE_MANAGE: 'ai.quality.badcase.manage',
  COST_MANAGE: 'ai.cost.manage',
  MODEL_POLICY_MANAGE: 'ai.model_policy.manage',
  RESTRICTED_CONTENT_REVEAL: 'ai.restricted_content.reveal',
  AUDIT_EXPORT: 'ai.audit.export',
} as const

type NamedCapability = (typeof AI_ADMIN_CAPABILITIES)[keyof typeof AI_ADMIN_CAPABILITIES]

interface NavItem {
  to: string
  label: string
  workspace: WorkspaceId
  /** Soft capability required; admins implicitly hold all. */
  capability?: NamedCapability
}

const NAV_ITEMS: NavItem[] = [
  { to: '/admin-console/command-center', label: '指挥中心', workspace: 'command-center', capability: AI_ADMIN_CAPABILITIES.OPERATIONS_READ },
  { to: '/admin-console/product-analytics', label: '产品分析', workspace: 'product-analytics', capability: AI_ADMIN_CAPABILITIES.SUPPORT_READ },
  { to: '/admin-console/ai-operations', label: 'AI 运营', workspace: 'ai-operations', capability: AI_ADMIN_CAPABILITIES.OPERATIONS_READ },
  { to: '/admin-console/model-policies', label: '模型策略', workspace: 'ai-operations', capability: AI_ADMIN_CAPABILITIES.MODEL_POLICY_MANAGE },
  { to: '/admin-console/incidents-badcases', label: '事件与差例', workspace: 'incidents-badcases', capability: AI_ADMIN_CAPABILITIES.QUALITY_BADCASE_MANAGE },
  { to: '/admin-console/logs-and-traces', label: '日志与链路', workspace: 'logs-and-traces', capability: AI_ADMIN_CAPABILITIES.OPERATIONS_READ },
  { to: '/admin-console/users-accounts', label: '用户与账户', workspace: 'users-accounts', capability: AI_ADMIN_CAPABILITIES.SUPPORT_READ },
  { to: '/admin-console/reports', label: '报告中心', workspace: 'reports', capability: AI_ADMIN_CAPABILITIES.AUDIT_EXPORT },
  { to: '/admin-console/governance', label: '治理与审计', workspace: 'governance', capability: AI_ADMIN_CAPABILITIES.AUDIT_EXPORT },
]

/** Four stable inspection workspace routes (must not be removed). */
export const INSPECTION_WORKSPACE_PATHS = [
  '/admin-console/ai-operations',
  '/admin-console/incidents-badcases',
  '/admin-console/logs-and-traces',
  '/admin-console/governance',
] as const

function currentTitle(pathname: string): string {
  const match = NAV_ITEMS.find((item) => item.to === pathname)
  if (match) return match.label
  if (pathname.startsWith('/admin-console/logs-and-traces')) return '日志与链路'
  if (pathname.startsWith('/admin-console/command-center')) return '指挥中心'
  if (pathname.startsWith('/admin-console/ai-release')) return 'AI 发布与灰度'
  if (pathname.startsWith('/admin-console/model-policies')) return '模型策略'
  return '管理后台'
}

function resolveCapabilities(user: { is_admin?: boolean; capabilities?: string[] } | null): Set<string> {
  if (!user) return new Set()
  if (user.is_admin) {
    return new Set(Object.values(AI_ADMIN_CAPABILITIES))
  }
  return new Set(user.capabilities ?? [])
}

export function AdminShell() {
  useCurrentUser()
  const user = useAuthStore((s) => s.user)
  const location = useLocation()
  const caps = resolveCapabilities(user as { is_admin?: boolean; capabilities?: string[] } | null)

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (!item.capability) return caps.size > 0
    return caps.has(item.capability)
  })

  return (
    <div className="ac-shell">
      <aside className="ac-shell__sidebar">
        <div className="ac-shell__brand">
          <span className="ac-shell__brand-mark" />
          <span>管理后台</span>
        </div>
        <nav className="ac-shell__nav" aria-label="admin-section" data-capability-gated="true">
          <div className="ac-shell__nav-label">运营</div>
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              data-capability={item.capability}
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
          if (p.startsWith('/admin-console/model-policies')) return <ModelPolicies />;
          if (p.startsWith('/admin-console/incidents-badcases')) return <IncidentsBadcases />;
          if (p.startsWith('/admin-console/logs-and-traces')) return <LogsAndTraces />;
          if (p.startsWith('/admin-console/users-accounts')) return <UsersAccounts />;
          if (p.startsWith('/admin-console/reports')) return <Reports />;
          if (p.startsWith('/admin-console/governance')) return <Governance />;
          if (p.startsWith('/admin-console/ai-release')) return <AIReleaseGovernance />;
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
      { path: 'model-policies', element: <ModelPolicies /> },
      { path: 'incidents-badcases', element: <IncidentsBadcases /> },
      { path: 'logs-and-traces', element: <LogsAndTraces /> },
      { path: 'users-accounts', element: <UsersAccounts /> },
      { path: 'reports', element: <Reports /> },
      { path: 'governance', element: <Governance /> },
      { path: 'ai-release', element: <AIReleaseGovernance /> },
    ],
  },
]

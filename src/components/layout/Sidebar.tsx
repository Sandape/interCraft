import { type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  MessageSquareText,
  Radar,
  Settings,
  Briefcase,
  ChevronsLeft,
  ChevronsRight,
  Layers3,
  BookOpen,
  HelpCircle,
  Search,
  BarChart3,
  Shield,
  Bot,
  ListTodo,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useResumeV2List } from '@/hooks/queries/useResumeV2List'
import { useAuthStore } from '@/stores/useAuthStore'

interface SidebarItem {
  to: string
  label: string
  icon: ReactNode
  badge?: number | string
  exact?: boolean
}

const secondaryNav: SidebarItem[] = [
  { to: '/jobs', label: '求职追踪', icon: <Briefcase className="h-4 w-4" /> },
  { to: '/ai-tasks', label: 'AI 任务', icon: <ListTodo className="h-4 w-4" /> },
  { to: '/agent', label: 'Agent 助手', icon: <Bot className="h-4 w-4" /> },
  { to: '/error-book', label: '错题本', icon: <BookOpen className="h-4 w-4" /> },
  { to: '/pm-dashboard', label: 'PM 看板', icon: <BarChart3 className="h-4 w-4" /> },
  { to: '/settings', label: '设置', icon: <Settings className="h-4 w-4" /> },
  { to: '/help', label: '帮助中心', icon: <HelpCircle className="h-4 w-4" /> },
]

export function Sidebar({
  collapsed,
  onToggle,
  onOpenSearch,
}: {
  collapsed: boolean
  onToggle: () => void
  onOpenSearch?: () => void
}) {
  // 036 Phase A.2 — single 简历中心 entry; v1 branch tree retired.
  // Count badge reflects the v2 resume list length.
  const { data: v2Resumes = [] } = useResumeV2List()
  const isAdmin = useAuthStore((s) => s.user?.is_admin === true)

  const primaryNav: SidebarItem[] = [
    { to: '/dashboard', label: '工作台', icon: <LayoutDashboard className="h-4 w-4" /> },
    { to: '/resume', label: '简历中心', icon: <FileText className="h-4 w-4" />, badge: v2Resumes.length },
    { to: '/interview', label: '模拟面试', icon: <MessageSquareText className="h-4 w-4" /> },
    { to: '/ability-profile', label: '个人画像', icon: <Radar className="h-4 w-4" /> },
  ]

  return (
    <aside
      className={cn(
        'flex flex-col h-full border-r border-surface-border dark:border-dark-surface-border',
        'bg-surface dark:bg-dark-surface transition-[width] duration-300 ease-out',
        collapsed ? 'w-14' : 'w-60',
      )}
    >
      {/* Logo */}
      <div className="h-14 flex items-center px-3.5 border-b border-surface-border dark:border-dark-surface-border flex-shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="h-7 w-7 rounded-md bg-brand-900 dark:bg-brand-200 flex items-center justify-center flex-shrink-0">
            <Layers3 className="h-3.5 w-3.5 text-white dark:text-brand-950" strokeWidth={1.8} />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-sm font-semibold text-ink-1 leading-tight">InterCraft</div>
              <div className="text-2xs text-ink-3 leading-tight">求职工作台</div>
            </div>
          )}
        </div>
      </div>

      {/* 主导航 */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {/* 搜索框 */}
        <div className="px-1">
          <button
            type="button"
            onClick={onOpenSearch}
            aria-label="搜索"
            className={cn(
              'flex h-9 w-full items-center rounded bg-surface-muted text-xs text-ink-3 transition-colors hover:text-ink-1 focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:bg-dark-surface-muted',
              collapsed ? 'justify-center px-0' : 'gap-2 px-2.5',
            )}
          >
            <Search className="h-3.5 w-3.5 flex-shrink-0" />
            {!collapsed && <span>搜索…</span>}
          </button>
        </div>

        {/* 主功能区 */}
        <div>
          {!collapsed && (
            <div className="px-2 mb-1 text-2xs font-semibold text-ink-3 uppercase tracking-wider">
              工作区
            </div>
          )}
          <div className="space-y-0.5">
            {primaryNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exact}
                aria-label={collapsed ? item.label : undefined}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 px-2 h-9 rounded text-sm transition-colors',
                    isActive
                      ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300 font-medium'
                      : 'text-ink-2 dark:text-dark-ink-secondary hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:text-ink-1 dark:hover:text-dark-ink-primary',
                  )
                }
              >
                <span className="flex-shrink-0">{item.icon}</span>
                {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                {!collapsed && item.badge !== undefined && (
                  <span className="text-2xs text-ink-3 dark:text-dark-ink-tertiary font-normal">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        </div>

        {/* 简历分支树已下线（v1 resume_branches 表退役，036 Phase A.2） */}

        {/* 次要导航 */}
        <div>
          {!collapsed && (
            <div className="px-2 mb-1 text-2xs font-semibold text-ink-3 uppercase tracking-wider">
              工具
            </div>
          )}
          <div className="space-y-0.5">
            {secondaryNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                aria-label={collapsed ? item.label : undefined}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 px-2 h-9 rounded text-sm transition-colors',
                    isActive
                      ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300 font-medium'
                      : 'text-ink-2 dark:text-dark-ink-secondary hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:text-ink-1 dark:hover:text-dark-ink-primary',
                  )
                }
              >
                <span className="flex-shrink-0">{item.icon}</span>
                {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
              </NavLink>
            ))}
            {/* FR-014: 管理后台入口 — 仅在 isAdmin 时可见 */}
            {isAdmin && (
              <NavLink
                to="/admin-console/command-center"
                aria-label={collapsed ? '管理后台' : undefined}
                title={collapsed ? '管理后台' : undefined}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 px-2 h-9 rounded text-sm transition-colors',
                    isActive
                      ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300 font-medium'
                      : 'text-ink-2 dark:text-dark-ink-secondary hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:text-ink-1 dark:hover:text-dark-ink-primary',
                  )
                }
              >
                <span className="flex-shrink-0"><Shield className="h-4 w-4" /></span>
                {!collapsed && <span className="flex-1 truncate">管理后台</span>}
              </NavLink>
            )}
          </div>
        </div>
      </nav>

      {/* 折叠按钮 */}
      <div className="border-t border-surface-border dark:border-dark-surface-border p-2 flex-shrink-0">
        <button
          onClick={onToggle}
          className={cn(
            'w-full flex items-center h-9 rounded text-xs text-ink-3',
            'hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary',
            'transition-colors',
            collapsed ? 'justify-center px-0' : 'gap-2 px-2',
          )}
          aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}
        >
          {collapsed ? <ChevronsRight className="h-3.5 w-3.5" /> : <ChevronsLeft className="h-3.5 w-3.5" />}
          {!collapsed && <span>折叠</span>}
        </button>
      </div>
    </aside>
  )
}

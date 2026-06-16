import { useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  MessageSquareText,
  Radar,
  Settings,
  Briefcase,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  Sparkles,
  BookOpen,
  HelpCircle,
  Plus,
  Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useResumeBranches } from '@/hooks/queries/useResumeBranches'

interface SidebarItem {
  to: string
  label: string
  icon: ReactNode
  badge?: number | string
  exact?: boolean
}

const secondaryNav: SidebarItem[] = [
  { to: '/jobs', label: '求职追踪', icon: <Briefcase className="h-4 w-4" /> },
  { to: '/error-book', label: '错题本', icon: <BookOpen className="h-4 w-4" /> },
  { to: '/settings', label: '设置', icon: <Settings className="h-4 w-4" /> },
  { to: '/help', label: '帮助中心', icon: <HelpCircle className="h-4 w-4" /> },
]

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const location = useLocation()
  const [resumesOpen, setResumesOpen] = useState(true)
  const activeResumeOnRoute = location.pathname.startsWith('/resume')
  const onResume = activeResumeOnRoute

  const { data: branches = [] } = useResumeBranches()

  const primaryNav: SidebarItem[] = [
    { to: '/dashboard', label: '工作台', icon: <LayoutDashboard className="h-4 w-4" /> },
    { to: '/resume', label: '简历中心', icon: <FileText className="h-4 w-4" />, badge: branches.length },
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
          <div className="h-7 w-7 rounded-md bg-gradient-to-br from-brand-900 to-brand-600 dark:from-brand-500 dark:to-brand-300 flex items-center justify-center flex-shrink-0 shadow-notion-sm">
            <Sparkles className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-sm font-semibold text-ink-1 leading-tight">InterCraft</div>
              <div className="text-2xs text-ink-3 leading-tight">面试工坊</div>
            </div>
          )}
        </div>
      </div>

      {/* 主导航 */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {/* 搜索框 */}
        {!collapsed && (
          <div className="px-1">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
              <input
                type="search"
                placeholder="搜索…"
                className="w-full h-7 pl-7 pr-2 text-xs rounded bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-shadow"
              />
            </div>
          </div>
        )}

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
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 px-2 h-7 rounded text-sm transition-colors',
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

        {/* 简历分支树（仅在简历页展开） */}
        {!collapsed && onResume && (
          <div className="animate-fade-in">
            <button
              onClick={() => setResumesOpen((v) => !v)}
              className="w-full flex items-center justify-between px-2 mb-1 group"
            >
              <span className="text-2xs font-semibold text-ink-3 uppercase tracking-wider">
                简历分支
              </span>
              <div className="flex items-center gap-1">
                <span
                  onClick={(e) => {
                    e.stopPropagation()
                  }}
                  className="p-0.5 rounded hover:bg-surface-muted text-ink-3 hover:text-ink-1 cursor-pointer"
                  role="button"
                  aria-label="新建分支"
                >
                  <Plus className="h-3 w-3" />
                </span>
                <ChevronDown
                  className={cn(
                    'h-3 w-3 text-ink-3 transition-transform',
                    !resumesOpen && '-rotate-90',
                  )}
                />
              </div>
            </button>
            {resumesOpen && (
              <div className="space-y-0.5">
                {branches.map((b) => {
                  const isActive = location.pathname === `/resume/${b.id}`
                  return (
                    <NavLink
                      key={b.id}
                      to={`/resume/${b.id}`}
                      className={cn(
                        'flex items-center gap-1.5 pl-5 pr-2 h-7 rounded text-xs transition-colors',
                        isActive
                          ? 'bg-surface-muted dark:bg-dark-surface-muted text-ink-1 font-medium'
                          : 'text-ink-3 dark:text-dark-ink-tertiary hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:text-ink-1 dark:hover:text-dark-ink-primary',
                      )}
                    >
                      <span
                        className={cn(
                          'h-1.5 w-1.5 rounded-full flex-shrink-0',
                          b.is_main
                            ? 'bg-brand-500'
                            : b.status === 'ready'
                              ? 'bg-emerald-500'
                              : b.status === 'optimizing'
                                ? 'bg-amber-500'
                                : b.status === 'submitted'
                                  ? 'bg-violet-500'
                                  : b.status === 'archived'
                                    ? 'bg-stone-400'
                                    : 'bg-ink-muted',
                        )}
                      />
                      <span className="truncate flex-1">{b.name}</span>
                    </NavLink>
                  )
                })}
              </div>
            )}
          </div>
        )}

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
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 px-2 h-7 rounded text-sm transition-colors',
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
          </div>
        </div>
      </nav>

      {/* 折叠按钮 */}
      <div className="border-t border-surface-border dark:border-dark-surface-border p-2 flex-shrink-0">
        <button
          onClick={onToggle}
          className={cn(
            'w-full flex items-center h-7 rounded text-xs text-ink-3',
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

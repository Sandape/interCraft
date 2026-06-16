import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Search, Command, HelpCircle, Plus, ChevronDown, Briefcase, FilePlus2 } from 'lucide-react'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { useAuthStore } from '@/stores/useAuthStore'
import { useLogout } from '@/hooks/mutations/useLogout'
import { useAvatarBlob } from '@/hooks/queries/useAvatarBlob'
import { useJobs } from '@/hooks/queries/useJobs'

export function Topbar({
  onOpenSearch,
}: {
  onOpenSearch?: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [newResumeMenu, setNewResumeMenu] = useState(false)
  const newResumeRef = useRef<HTMLDivElement>(null)
  const notificationsRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const logout = useLogout()
  const avatarSrc = useAvatarBlob(user?.avatar_url ?? null)
  const { data: jobsData, isLoading: jobsLoading } = useJobs({ limit: 10 })
  const jobs = jobsData?.data ?? []

  const displayName = user?.display_name ?? user?.email.split('@')[0] ?? '未登录'
  const title = user?.title ?? user?.target_role ?? ''
  const initials = displayName.slice(0, 1).toUpperCase()

  function handleLogout() {
    setMenuOpen(false)
    logout.mutate(undefined, {
      onSuccess: () => navigate('/login', { replace: true }),
    })
  }

  function goTo(path: string) {
    setMenuOpen(false)
    setNotificationsOpen(false)
    navigate(path)
  }

  useEffect(() => {
    if (!notificationsOpen) return

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setNotificationsOpen(false)
    }

    function handlePointerDown(event: MouseEvent) {
      if (!notificationsRef.current?.contains(event.target as Node)) {
        setNotificationsOpen(false)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('mousedown', handlePointerDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('mousedown', handlePointerDown)
    }
  }, [notificationsOpen])

  return (
    <header className="h-14 border-b border-surface-border dark:border-dark-surface-border bg-surface/80 dark:bg-dark-surface/80 backdrop-blur-md flex items-center px-6 flex-shrink-0 sticky top-0 z-30">
      {/* Breadcrumb / Page context */}
      <div className="flex items-center gap-2 text-sm text-ink-3 dark:text-dark-ink-tertiary min-w-0">
        <span className="text-ink-1 dark:text-dark-ink-primary font-medium truncate">
          {displayName}
          {title && (
            <span className="text-ink-3 dark:text-dark-ink-tertiary font-normal ml-1.5">
              · {title}
            </span>
          )}
        </span>
      </div>

      {/* 中心搜索 */}
      <div className="flex-1 max-w-md mx-8 hidden md:block">
        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
          <input
            type="search"
            data-testid="topbar-search-input"
            placeholder="搜索简历、面试记录、能力维度…"
            onClick={() => onOpenSearch?.()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onOpenSearch?.()
              }
            }}
            readOnly
            className="w-full h-8 pl-9 pr-16 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:bg-surface dark:focus:bg-dark-surface transition-all cursor-pointer"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 hidden lg:inline-flex items-center gap-0.5 px-1.5 h-5 rounded text-2xs font-medium text-ink-3 dark:text-dark-ink-tertiary bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border">
            <Command className="h-2.5 w-2.5" />K
          </kbd>
        </div>
      </div>

      <div className="flex-1 md:hidden" />

      {/* 右侧操作 */}
      <div className="flex items-center gap-1">
        {/* 019 — 新建简历下拉 (US2: 空白创建 / 基于岗位创建) */}
        <div className="relative" ref={newResumeRef}>
          <Button
            size="sm"
            variant="primary"
            leftIcon={<Plus className="h-3.5 w-3.5" />}
            rightIcon={<ChevronDown className="h-3 w-3" />}
            data-testid="topbar-new-resume-button"
            onClick={() => setNewResumeMenu((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={newResumeMenu}
          >
            <span className="hidden sm:inline">新建简历</span>
          </Button>
          {newResumeMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setNewResumeMenu(false)} />
              <div
                data-testid="topbar-new-resume-menu"
                role="menu"
                className="absolute right-0 top-full mt-1.5 w-64 z-50 surface-1 rounded-md border border-surface-border dark:border-dark-surface-border shadow-notion-md py-1.5 animate-fade-in"
              >
                <MenuItem
                  testId="topbar-new-resume-blank"
                  onClick={() => { setNewResumeMenu(false); navigate('/resume?new=true') }}
                >
                  <div className="flex items-center gap-2">
                    <FilePlus2 className="h-3.5 w-3.5" />
                    <span>空白创建</span>
                  </div>
                </MenuItem>
                <div className="px-3 pt-1.5 pb-1 text-2xs text-ink-3 uppercase tracking-wide">
                  基于岗位创建
                </div>
                <div className="max-h-60 overflow-y-auto" data-testid="topbar-new-resume-from-job">
                  {jobsLoading ? (
                    <div className="px-3 py-2 text-xs text-ink-3">加载中…</div>
                  ) : jobs.length === 0 ? (
                    <div className="px-3 py-2 text-xs text-ink-3">暂无岗位,请先在「求职追踪」中登记</div>
                  ) : (
                    jobs.map((j) => (
                      <MenuItem
                        key={j.id}
                        testId={`topbar-new-resume-from-job-${j.id}`}
                        onClick={() => {
                          setNewResumeMenu(false)
                          navigate(`/resume?new=true&source_job_id=${j.id}`)
                        }}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Briefcase className="h-3.5 w-3.5 flex-shrink-0" />
                          <div className="min-w-0">
                            <div className="truncate text-ink-1">{j.company} · {j.position}</div>
                            {j.base_location && (
                              <div className="text-2xs text-ink-3 truncate">{j.base_location}</div>
                            )}
                          </div>
                        </div>
                      </MenuItem>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <button
          type="button"
          data-testid="topbar-help-button"
          onClick={() => goTo('/help')}
          className="hidden sm:inline-flex h-7 w-7 items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary transition-colors"
          aria-label="帮助"
        >
          <HelpCircle className="h-4 w-4" />
        </button>

        <div className="relative" ref={notificationsRef}>
          <button
            type="button"
            data-testid="topbar-notifications-button"
            onClick={() => {
              setMenuOpen(false)
              setNotificationsOpen((v) => !v)
            }}
            className="relative h-7 w-7 inline-flex items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary transition-colors"
            aria-label="通知"
            aria-expanded={notificationsOpen}
            aria-haspopup="dialog"
          >
            <Bell className="h-4 w-4" />
            <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-brand-500" />
          </button>
          {notificationsOpen && (
            <div
              data-testid="topbar-notifications-panel"
              role="dialog"
              aria-label="通知中心"
              className="absolute right-0 top-full mt-1.5 w-72 z-50 surface-1 rounded-md border border-surface-border dark:border-dark-surface-border shadow-notion-md p-3 animate-fade-in"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-ink-1">通知中心</div>
                  <div className="text-xs text-ink-3 mt-0.5">暂无新的待处理通知</div>
                </div>
                <span className="h-5 min-w-5 px-1.5 rounded-full bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300 text-2xs font-semibold inline-flex items-center justify-center">
                  0
                </span>
              </div>
              <div className="mt-3 rounded-md bg-surface-muted dark:bg-dark-surface-muted px-3 py-2 text-xs text-ink-3 leading-relaxed">
                面试提醒、报告生成和简历优化结果会出现在这里。
              </div>
              <button
                type="button"
                data-testid="topbar-notifications-settings"
                onClick={() => goTo('/settings?tab=notifications')}
                className="mt-3 w-full text-left px-3 py-2 rounded-md text-sm text-brand-600 dark:text-brand-300 hover:bg-brand-50 dark:hover:bg-brand-500/10 transition-colors"
              >
                管理通知设置
              </button>
            </div>
          )}
        </div>

        <ThemeToggle />

        <div className="relative ml-1">
          <button
            type="button"
            data-testid="topbar-user-menu-button"
            onClick={() => {
              setNotificationsOpen(false)
              setMenuOpen((v) => !v)
            }}
            className="flex items-center gap-2 p-0.5 rounded hover:bg-surface-muted dark:hover:bg-dark-surface-muted transition-colors"
            aria-label="用户菜单"
            aria-expanded={menuOpen}
            aria-haspopup="menu"
          >
            <Avatar name={initials} size="sm" src={avatarSrc ?? undefined} />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div
                className="absolute right-0 top-full mt-1.5 w-60 z-50 surface-1 rounded-md border border-surface-border dark:border-dark-surface-border shadow-notion-md py-1.5 animate-fade-in"
                data-testid="topbar-user-menu"
                role="menu"
              >
                <div className="px-3 py-2 border-b border-surface-border dark:border-dark-surface-border">
                  <div className="text-sm font-medium text-ink-1">{displayName}</div>
                  <div className="text-xs text-ink-3 mt-0.5 truncate">{user?.email ?? ''}</div>
                  {user?.subscription && (
                    <div className="mt-2 inline-flex items-center gap-1 tag-brand">
                      <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                      {user.subscription} 会员
                    </div>
                  )}
                </div>
                <div className="py-1">
                  <MenuItem data-testid="topbar-menu-profile" onClick={() => goTo('/profile')}>个人资料</MenuItem>
                  <MenuItem data-testid="topbar-menu-settings" onClick={() => goTo('/settings?tab=profile')}>账户设置</MenuItem>
                  <MenuItem data-testid="topbar-menu-subscription" onClick={() => goTo('/settings?tab=subscription')}>升级到 Enterprise</MenuItem>
                  <MenuItem data-testid="topbar-menu-export" onClick={() => goTo('/settings?tab=export')}>数据导出</MenuItem>
                </div>
                <div className="border-t border-surface-border dark:border-dark-surface-border py-1">
                  <MenuItem testId="topbar-menu-logout" onClick={handleLogout} disabled={logout.isPending}>
                    {logout.isPending ? '正在退出…' : '退出登录'}
                  </MenuItem>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

function MenuItem({
  children,
  danger,
  onClick,
  disabled,
  'data-testid': testId,
}: {
  children: React.ReactNode
  danger?: boolean
  onClick?: () => void
  disabled?: boolean
  'data-testid'?: string
  testId?: string
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      role="menuitem"
      onClick={onClick}
      disabled={disabled}
      className={
        'w-full text-left px-3 py-1.5 text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed ' +
        (danger
          ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10'
          : 'text-ink-2 dark:text-dark-ink-secondary hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:text-ink-1 dark:hover:text-dark-ink-primary')
      }
    >
      {children}
    </button>
  )
}

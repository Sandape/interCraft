import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Search, Command, HelpCircle, Plus, Shield, Coins } from 'lucide-react'
import { accountApi } from '@/api/account'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useAuthStore } from '@/stores/useAuthStore'
import { useLogout } from '@/hooks/mutations/useLogout'
import { useAvatarBlob } from '@/hooks/queries/useAvatarBlob'
import { useAIPointAccount } from '@/hooks/queries/useAIPoints'
import { timeAgo } from '@/lib/utils'

export function Topbar({
  onOpenSearch,
}: {
  onOpenSearch?: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const notificationsRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const logout = useLogout()
  const avatarSrc = useAvatarBlob(user?.avatar_url ?? null)
  const notificationsQuery = useQuery({
    queryKey: ['account', 'notifications'],
    queryFn: accountApi.getNotificationCenter,
    staleTime: 30_000,
  })
  const markNotificationRead = useMutation({
    mutationFn: (notificationId: string) => accountApi.markNotificationRead(notificationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['account', 'notifications'] }),
  })
  const notifications = notificationsQuery.data?.notifications ?? []
  const unreadCount = notificationsQuery.data?.unread_count ?? 0
  const pointsQuery = useAIPointAccount({ enabled: Boolean(user) })
  const pointAccount = pointsQuery.data

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
        {/* REQ-061 US8 — Pro + 新用户体验 + point summary (no upgrade CTA). */}
        {user && (
          <button
            type="button"
            data-testid="topbar-ai-points"
            onClick={() => goTo('/ai-points')}
            className="hidden sm:inline-flex items-center gap-1.5 h-7 px-2 rounded text-xs text-ink-2 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary transition-colors mr-0.5"
            aria-label="体验点数"
          >
            <Coins className="h-3.5 w-3.5 text-brand-500" />
            <span className="font-medium">
              {pointAccount?.plan_label ?? 'Pro'}
            </span>
            <Badge variant="brand" className="!text-[10px] !py-0 !px-1.5 !h-4">
              {pointAccount?.experience_badge ?? '新用户体验'}
            </Badge>
            <span className="tabular-nums text-ink-3">
              {pointsQuery.isPending
                ? '…'
                : pointsQuery.isError
                  ? '—'
                  : `${(pointAccount?.available ?? 0).toLocaleString()} 点`}
            </span>
          </button>
        )}

        {/* 036 US4 — single "新建简历" button; opens the Template Gallery modal
            inside ResumeList via ?new=true. No dropdown / no v1 split. */}
        <Button
          size="sm"
          variant="primary"
          leftIcon={<Plus className="h-3.5 w-3.5" />}
          data-testid="topbar-new-resume-button"
          onClick={() => navigate('/resume?new=true')}
        >
          <span className="hidden sm:inline">新建简历</span>
        </Button>

        <button
          type="button"
          data-testid="topbar-help-button"
          onClick={() => goTo('/help')}
          className="hidden sm:inline-flex h-7 w-7 items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary transition-colors"
          aria-label="帮助"
        >
          <HelpCircle className="h-4 w-4" />
        </button>

        {/* REQ-051: admin console entry — shield icon, visible only to admin users. */}
        {user?.is_admin && (
          <button
            type="button"
            data-testid="topbar-admin-console-button"
            onClick={() => goTo('/admin-console/command-center')}
            className="hidden sm:inline-flex h-7 w-7 items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary transition-colors"
            aria-label="管理后台"
          >
            <Shield className="h-4 w-4" />
          </button>
        )}

        <div className="relative" ref={notificationsRef}>
          <button
            type="button"
            data-testid="topbar-notifications-button"
            onClick={() => {
              setMenuOpen(false)
              setNotificationsOpen((v) => !v)
            }}
            className="relative h-7 w-7 inline-flex items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary transition-colors"
            aria-label={`通知，${unreadCount} 条未读`}
            aria-expanded={notificationsOpen}
            aria-haspopup="dialog"
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <span
                data-testid="topbar-unread-count"
                className="absolute -right-1.5 -top-1.5 min-w-4 h-4 px-1 rounded-full bg-red-600 text-white text-[10px] font-semibold leading-4 text-center"
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
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
                  <div className="text-xs text-ink-3 mt-0.5">{unreadCount} 条未读</div>
                </div>
              </div>
              {notificationsQuery.isPending ? (
                <div className="mt-3 px-3 py-4 text-center text-xs text-ink-3">正在加载通知…</div>
              ) : notificationsQuery.isError ? (
                <div className="mt-3 rounded-md bg-surface-muted dark:bg-dark-surface-muted px-3 py-3 text-xs text-ink-3">
                  <div>通知加载失败，请稍后重试。</div>
                  <button
                    type="button"
                    onClick={() => notificationsQuery.refetch()}
                    className="mt-2 text-brand-600 dark:text-brand-300 hover:underline"
                  >
                    重新加载
                  </button>
                </div>
              ) : notifications.length === 0 ? (
                <div className="mt-3 rounded-md bg-surface-muted dark:bg-dark-surface-muted px-3 py-2 text-xs text-ink-3 leading-relaxed">
                  <div className="font-medium text-ink-2 dark:text-dark-ink-secondary">暂无新的待处理通知</div>
                  <div className="mt-1">面试提醒、报告生成和简历优化结果会出现在这里。</div>
                </div>
              ) : (
                <div className="mt-3 max-h-80 space-y-1.5 overflow-y-auto">
                  {notifications.map((notification) => (
                    <button
                      key={notification.id}
                      type="button"
                      aria-label={`${notification.title}${notification.is_read ? '' : '，未读'}`}
                      onClick={() => {
                        if (!notification.is_read) markNotificationRead.mutate(notification.id)
                      }}
                      className={`w-full rounded-md px-3 py-2 text-left transition-colors hover:bg-surface-muted dark:hover:bg-dark-surface-muted ${
                        notification.is_read ? 'opacity-70' : 'bg-brand-50/60 dark:bg-brand-500/10'
                      }`}
                    >
                      <span className="flex items-start gap-2">
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-ink-1">{notification.title}</span>
                          <span className="mt-0.5 block line-clamp-2 text-xs leading-relaxed text-ink-3">{notification.message}</span>
                          <span className="mt-1 block text-2xs text-ink-muted">{timeAgo(notification.created_at)}</span>
                        </span>
                        {!notification.is_read && <span className="mt-1 h-2 w-2 flex-none rounded-full bg-brand-500" aria-hidden="true" />}
                      </span>
                    </button>
                  ))}
                </div>
              )}
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
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="inline-flex items-center gap-1 tag-brand">
                      <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                      {pointAccount?.plan_label ?? 'Pro'}
                    </span>
                    <span className="text-2xs text-ink-3">
                      {pointAccount?.experience_badge ?? '新用户体验'}
                    </span>
                    {!pointsQuery.isPending && !pointsQuery.isError && pointAccount && (
                      <span className="text-2xs text-ink-3 tabular-nums">
                        · {pointAccount.available.toLocaleString()} 点可用
                      </span>
                    )}
                  </div>
                </div>
                <div className="py-1">
                  {/* REQ-051: admin console entry in user dropdown. */}
                  {user?.is_admin ? (
                    <MenuItem data-testid="topbar-menu-admin-console" onClick={() => goTo('/admin-console/command-center')}>
                      <Shield className="h-3.5 w-3.5 mr-1.5 inline" />
                      管理后台
                    </MenuItem>
                  ) : (
                    <MenuItem data-testid="topbar-menu-admin-console" disabled>
                      <Shield className="h-3.5 w-3.5 mr-1.5 inline" />
                      管理后台
                    </MenuItem>
                  )}
                  <MenuItem data-testid="topbar-menu-profile" onClick={() => goTo('/ability-profile')}>个人画像</MenuItem>
                  <MenuItem data-testid="topbar-menu-settings" onClick={() => goTo('/settings?tab=profile')}>账户设置</MenuItem>
                  <MenuItem data-testid="topbar-menu-subscription" onClick={() => goTo('/ai-points')}>体验点数</MenuItem>
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
  'data-testid': dataTestId,
  testId,
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
      data-testid={dataTestId ?? testId}
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

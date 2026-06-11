import { useState } from 'react'
import { Bell, Search, Command, HelpCircle, Plus } from 'lucide-react'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { Avatar } from '@/components/ui/Avatar'
import { currentUser } from '@/data/mockData'
import { Button } from '@/components/ui/Button'

export function Topbar({ onNewResume }: { onNewResume?: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false)
  return (
    <header className="h-14 border-b border-surface-border dark:border-dark-surface-border bg-surface/80 dark:bg-dark-surface/80 backdrop-blur-md flex items-center px-6 flex-shrink-0 sticky top-0 z-30">
      {/* Breadcrumb / Page context */}
      <div className="flex items-center gap-2 text-sm text-ink-3 dark:text-dark-ink-tertiary min-w-0">
        <span className="text-ink-1 dark:text-dark-ink-primary font-medium truncate">
          {currentUser.name}
          <span className="text-ink-3 dark:text-dark-ink-tertiary font-normal ml-1.5">
            · {currentUser.title}
          </span>
        </span>
      </div>

      {/* 中心搜索 */}
      <div className="flex-1 max-w-md mx-8 hidden md:block">
        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted" />
          <input
            type="search"
            placeholder="搜索简历、面试记录、能力维度…"
            className="w-full h-8 pl-9 pr-16 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:bg-surface dark:focus:bg-dark-surface transition-all"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 hidden lg:inline-flex items-center gap-0.5 px-1.5 h-5 rounded text-2xs font-medium text-ink-3 dark:text-dark-ink-tertiary bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border">
            <Command className="h-2.5 w-2.5" />K
          </kbd>
        </div>
      </div>

      <div className="flex-1 md:hidden" />

      {/* 右侧操作 */}
      <div className="flex items-center gap-1">
        <Button size="sm" variant="primary" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={onNewResume}>
          新建简历分支
        </Button>

        <button
          className="hidden sm:inline-flex h-7 w-7 items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary transition-colors"
          aria-label="帮助"
        >
          <HelpCircle className="h-4 w-4" />
        </button>

        <button
          className="relative h-7 w-7 inline-flex items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary transition-colors"
          aria-label="通知"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-brand-500" />
        </button>

        <ThemeToggle />

        <div className="relative ml-1">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 p-0.5 rounded hover:bg-surface-muted dark:hover:bg-dark-surface-muted transition-colors"
            aria-label="用户菜单"
          >
            <Avatar name={currentUser.name} size="sm" />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1.5 w-60 z-50 surface-1 rounded-md border border-surface-border dark:border-dark-surface-border shadow-notion-md py-1.5 animate-fade-in">
                <div className="px-3 py-2 border-b border-surface-border dark:border-dark-surface-border">
                  <div className="text-sm font-medium text-ink-1">{currentUser.name}</div>
                  <div className="text-xs text-ink-3 mt-0.5 truncate">{currentUser.email}</div>
                  <div className="mt-2 inline-flex items-center gap-1 tag-brand">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                    {currentUser.subscription} 会员
                  </div>
                </div>
                <div className="py-1">
                  <MenuItem>个人资料</MenuItem>
                  <MenuItem>账户设置</MenuItem>
                  <MenuItem>升级到 Enterprise</MenuItem>
                  <MenuItem>数据导出</MenuItem>
                </div>
                <div className="border-t border-surface-border dark:border-dark-surface-border py-1">
                  <MenuItem danger>退出登录</MenuItem>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

function MenuItem({ children, danger }: { children: React.ReactNode; danger?: boolean }) {
  return (
    <button
      className={
        'w-full text-left px-3 py-1.5 text-sm transition-colors ' +
        (danger
          ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10'
          : 'text-ink-2 dark:text-dark-ink-secondary hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:text-ink-1 dark:hover:text-dark-ink-primary')
      }
    >
      {children}
    </button>
  )
}

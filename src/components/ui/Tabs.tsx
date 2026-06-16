import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Tab {
  key: string
  label: ReactNode
  count?: number
}

interface TabsProps {
  items: Tab[]
  value: string
  onChange: (key: string) => void
  className?: string
  size?: 'sm' | 'md'
  getTabId?: (key: string) => string | undefined
}

export function Tabs({ items, value, onChange, className, size = 'md', getTabId }: TabsProps) {
  return (
    <div className={cn('flex items-center gap-0.5', className)} role="tablist">
      {items.map((item) => {
        const active = item.key === value
        return (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
            role="tab"
            aria-selected={active}
            data-testid={getTabId?.(item.key)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded font-medium transition-all duration-200',
              size === 'sm' ? 'h-7 px-2.5 text-xs' : 'h-8 px-3 text-sm',
              active
                ? 'bg-surface-muted text-ink-1 dark:bg-dark-surface-muted dark:text-dark-ink-primary'
                : 'text-ink-3 hover:text-ink-1 hover:bg-surface-muted/60 dark:hover:text-dark-ink-primary dark:hover:bg-dark-surface-muted/40',
            )}
          >
            {item.label}
            {typeof item.count === 'number' && (
              <span
                className={cn(
                  'inline-flex items-center justify-center min-w-4 h-4 px-1 rounded text-2xs font-medium',
                  active
                    ? 'bg-brand-500/15 text-brand-600 dark:text-brand-300'
                    : 'bg-surface-muted text-ink-3 dark:bg-dark-surface-muted dark:text-dark-ink-tertiary',
                )}
              >
                {item.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

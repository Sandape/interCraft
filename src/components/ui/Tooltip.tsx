import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * 简单的标题提示包装器 - 鼠标悬停显示完整文本
 */
export function Tooltip({
  children,
  content,
  className,
}: {
  children: ReactNode
  content: ReactNode
  className?: string
}) {
  return (
    <span className={cn('relative group inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute left-1/2 top-full z-50 mt-1.5 -translate-x-1/2',
          'whitespace-nowrap rounded bg-ink-primary dark:bg-dark-ink-primary px-2 py-1',
          'text-2xs font-medium text-white dark:text-ink-primary shadow-notion',
          'opacity-0 group-hover:opacity-100 transition-opacity duration-200',
        )}
      >
        {content}
      </span>
    </span>
  )
}

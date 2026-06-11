import { type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const padMap = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}

export function Card({ hover, padding = 'md', className, children, ...rest }: CardProps) {
  return (
    <div className={cn(hover ? 'card-hover' : 'card', padMap[padding], className)} {...rest}>
      {children}
    </div>
  )
}

export function CardHeader({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-start justify-between gap-3 mb-3', className)}>
      <div className="min-w-0">
        <div className="text-sm font-semibold text-ink-1">{title}</div>
        {description && <div className="text-xs text-ink-3 mt-0.5">{description}</div>}
      </div>
      {action}
    </div>
  )
}

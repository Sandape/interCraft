import { type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

type Variant = 'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant
  leftIcon?: ReactNode
}

const variantClass: Record<Variant, string> = {
  default: 'tag-default',
  brand: 'tag-brand',
  success: 'tag-success',
  warning: 'tag-warning',
  danger: 'tag-danger',
  outline: 'tag bg-transparent border border-surface-border text-ink-secondary',
}

export function Badge({ variant = 'default', leftIcon, className, children, ...rest }: BadgeProps) {
  return (
    <span className={cn(variantClass[variant], className)} {...rest}>
      {leftIcon}
      {children}
    </span>
  )
}

import { cn } from '@/lib/utils'

interface ProgressProps {
  value: number // 0-100
  size?: 'sm' | 'md'
  variant?: 'default' | 'brand' | 'success' | 'warning' | 'danger'
  className?: string
}

const variantMap = {
  default: 'bg-ink-primary',
  brand: 'bg-brand-500',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  danger: 'bg-red-500',
}

export function Progress({ value, size = 'md', variant = 'default', className }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value))
  return (
    <div
      className={cn(
        'w-full overflow-hidden rounded-full bg-surface-muted',
        size === 'sm' ? 'h-1' : 'h-1.5',
        className,
      )}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn('h-full rounded-full transition-all duration-500 ease-out', variantMap[variant])}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}

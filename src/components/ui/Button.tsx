import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  leftIcon?: ReactNode
  rightIcon?: ReactNode
  loading?: boolean
}

const variantClass: Record<Variant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
}

const sizeClass: Record<Size, string> = {
  sm: 'btn-sm',
  md: 'btn-md',
  lg: 'btn-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { variant = 'secondary', size = 'md', leftIcon, rightIcon, loading, className, children, disabled, ...rest },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        className={cn(variantClass[variant], sizeClass[size], className)}
        disabled={disabled || loading}
        {...rest}
      >
        {loading ? (
          <span
            className="inline-block h-3 w-3 rounded-full border-2 border-current border-r-transparent animate-spin"
            aria-hidden
          />
        ) : (
          leftIcon
        )}
        {children}
        {!loading && rightIcon}
      </button>
    )
  },
)
Button.displayName = 'Button'

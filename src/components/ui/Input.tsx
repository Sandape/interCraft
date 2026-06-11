import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

type Size = 'sm' | 'md' | 'lg'

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  size?: Size
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

const sizeMap: Record<Size, string> = {
  sm: 'input-sm',
  md: 'input-md',
  lg: 'input-lg',
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ size = 'md', leftIcon, rightIcon, className, ...rest }, ref) => {
    if (leftIcon || rightIcon) {
      return (
        <div className={cn('relative w-full', className)}>
          {leftIcon && (
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none">
              {leftIcon}
            </span>
          )}
          <input
            ref={ref}
            className={cn(
              sizeMap[size],
              leftIcon && 'pl-8',
              rightIcon && 'pr-8',
            )}
            {...rest}
          />
          {rightIcon && (
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-muted">
              {rightIcon}
            </span>
          )}
        </div>
      )
    }
    return <input ref={ref} className={cn(sizeMap[size], className)} {...rest} />
  },
)
Input.displayName = 'Input'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  size?: Size
}

const taSizeMap: Record<Size, string> = {
  sm: 'min-h-[60px] p-2 text-xs rounded border border-surface-border bg-transparent',
  md: 'min-h-[80px] p-2.5 text-sm rounded border border-surface-border bg-transparent',
  lg: 'min-h-[120px] p-3 text-sm rounded border border-surface-border bg-transparent',
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ size = 'md', className, ...rest }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          taSizeMap[size],
          'w-full text-ink-1 placeholder:text-ink-muted resize-y',
          'focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/15',
          'transition-all duration-200',
          className,
        )}
        {...rest}
      />
    )
  },
)
Textarea.displayName = 'Textarea'

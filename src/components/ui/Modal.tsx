import { type ReactNode, useEffect, useId } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}

const sizeMap = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
}

export function Modal({ open, onClose, title, description, children, footer, size = 'md' }: ModalProps) {
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-100 flex items-center justify-center p-4 animate-fade-in">
      <div
        className="absolute inset-0 bg-black/40 dark:bg-black/60 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden
      />
      <div
        className={cn(
          'relative w-full bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border rounded-lg shadow-notion-lg animate-fade-in',
          sizeMap[size],
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descriptionId : undefined}
      >
        {(title || description) && (
          <div className="px-5 pt-5 pb-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                {title && <h2 id={titleId} className="text-base font-semibold text-ink-1">{title}</h2>}
                {description && <p id={descriptionId} className="text-xs text-ink-3 mt-1">{description}</p>}
              </div>
              <button
                onClick={onClose}
                className="p-1 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
        <div className="px-5 pb-5">{children}</div>
        {footer && <div className="px-5 py-3 border-t border-surface-border dark:border-dark-surface-border flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  )
}

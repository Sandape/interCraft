import { type ReactNode, useEffect, useId, useRef } from 'react'
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
  const dialogRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    previousFocusRef.current = document.activeElement as HTMLElement | null
    const previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const focusable = () => Array.from(
      dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) ?? [],
    ).filter((element) => !element.hasAttribute('hidden'))

    const frame = window.requestAnimationFrame(() => focusable()[0]?.focus())
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      const elements = focusable()
      if (!elements.length) {
        event.preventDefault()
        dialogRef.current?.focus()
        return
      }
      const first = elements[0]
      const last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousBodyOverflow
      previousFocusRef.current?.focus()
    }
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 animate-fade-in">
      <div
        className="absolute inset-0 bg-black/40 dark:bg-black/60 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden
      />
      <div
        ref={dialogRef}
        tabIndex={-1}
        className={cn(
          'relative flex max-h-[calc(100dvh-2rem)] w-full flex-col bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border rounded-lg shadow-notion-lg animate-fade-in',
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
                type="button"
                onClick={onClose}
                className="p-1 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
        <div className="min-h-0 overflow-y-auto px-5 pb-5">{children}</div>
        {footer && <div className="flex flex-shrink-0 justify-end gap-2 border-t border-surface-border px-5 py-3 dark:border-dark-surface-border">{footer}</div>}
      </div>
    </div>
  )
}

import { Check, X } from 'lucide-react'
import { RESUME_STYLES, getStyleById, DEFAULT_STYLE_ID } from '@/modules/resume/styles'
import { cn } from '@/lib/utils'

interface StyleSelectorProps {
  selectedStyleId?: string
  onSelect: (styleId: string) => void
  open: boolean
  onClose: () => void
  className?: string
}

export default function StyleSelector({
  selectedStyleId = DEFAULT_STYLE_ID,
  onSelect,
  open,
  onClose,
  className,
}: StyleSelectorProps) {
  if (!open) return null

  const selected = getStyleById(selectedStyleId)

  return (
    <div className="fixed inset-0 z-50" onClick={onClose}>
      <div
        className={cn(
          'absolute right-4 top-12 w-[380px] bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border rounded-lg shadow-notion-lg z-50',
          className,
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border dark:border-dark-surface-border">
          <div>
            <h3 className="text-sm font-semibold text-ink-1">选择样式</h3>
            <p className="text-2xs text-ink-3 mt-0.5">
              当前：{selected?.labelZh ?? '未知'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-muted text-ink-3 hover:text-ink-1"
            aria-label="关闭"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 p-4">
          {RESUME_STYLES.map((style) => {
            const isActive = style.id === selectedStyleId
            return (
              <button
                key={style.id}
                onClick={() => {
                  onSelect(style.id)
                  onClose()
                }}
                className={cn(
                  'text-left p-3 rounded-md border transition-all group',
                  isActive
                    ? 'border-brand-500 bg-brand-50/50 dark:bg-brand-500/10 ring-1 ring-brand-500/30'
                    : 'border-surface-border dark:border-dark-surface-border hover:border-ink-300 dark:hover:border-dark-ink-muted hover:bg-surface-subtle',
                )}
              >
                <div className="flex items-start gap-2.5">
                  <StyleThumbnail styleId={style.id} active={isActive} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1">
                      <span className="text-xs font-medium text-ink-1">{style.labelZh}</span>
                      {isActive && <Check className="h-3 w-3 text-brand-500 flex-shrink-0" />}
                    </div>
                    <p className="text-2xs text-ink-3 mt-0.5 leading-snug">{style.description}</p>
                  </div>
                </div>
              </button>
            )
          })}
        </div>

        {/* Footer with comparison hint */}
        <div className="px-4 py-2.5 border-t border-surface-border dark:border-dark-surface-border text-2xs text-ink-3">
          字节、阿里等偏好现代双栏；外企、研究岗推荐编辑式；海投首选紧凑一页
        </div>
      </div>
    </div>
  )
}

function StyleThumbnail({ styleId, active }: { styleId: string; active: boolean }) {
  const borderColor = active ? 'border-brand-400' : 'border-ink-200 dark:border-ink-700'

  if (styleId === 'modern-two-column') {
    return (
      <div className={cn('w-10 h-13 rounded-xs border bg-white dark:bg-ink-50 shrink-0 p-0.5', borderColor)}>
        <div className="flex gap-0.5 h-full">
          <div className="w-[30%] bg-ink-100 dark:bg-ink-200 rounded-xs" />
          <div className="flex-1 space-y-0.5">
            <div className="h-0.5 w-full bg-ink-200 dark:bg-ink-400 rounded-xs" />
            <div className="h-0.5 w-3/4 bg-ink-200 dark:bg-ink-400 rounded-xs" />
            <div className="h-0.5 w-1/2 bg-ink-200 dark:bg-ink-400 rounded-xs" />
            <div className="h-0.5 w-2/3 bg-ink-200 dark:bg-ink-400 rounded-xs mt-0.5" />
          </div>
        </div>
      </div>
    )
  }

  if (styleId === 'editorial') {
    return (
      <div className={cn('w-10 h-13 rounded-xs border bg-white dark:bg-ink-50 shrink-0 p-1', borderColor)}>
        <div className="space-y-0.5">
          <div className="h-1 w-2/3 bg-ink-300 dark:bg-ink-600 rounded-xs italic" style={{ fontFamily: 'serif' }} />
          <div className="h-0.5 w-1/2 bg-ink-200 dark:bg-ink-700 rounded-xs" />
          <div className="h-px bg-ink-200 dark:bg-ink-700 my-0.5" />
          <div className="h-0.5 w-full bg-ink-200 dark:bg-ink-700 rounded-xs" />
          <div className="h-0.5 w-3/4 bg-ink-200 dark:bg-ink-700 rounded-xs" />
        </div>
      </div>
    )
  }

  if (styleId === 'compact-one-page') {
    return (
      <div className={cn('w-10 h-13 rounded-xs border bg-white dark:bg-ink-50 shrink-0 p-1', borderColor)}>
        <div className="space-y-0.5">
          <div className="h-0.5 w-2/3 bg-ink-300 dark:bg-ink-600 rounded-xs mx-auto" />
          <div className="h-0.5 w-1/3 bg-ink-200 dark:bg-ink-700 rounded-xs mx-auto" />
          <div className="h-px bg-ink-300 dark:bg-ink-600 my-0.5" />
          <div className="h-0.5 w-full bg-ink-200 dark:bg-ink-700 rounded-xs" />
          <div className="h-0.5 w-full bg-ink-200 dark:bg-ink-700 rounded-xs" />
          <div className="h-0.5 w-full bg-ink-200 dark:bg-ink-700 rounded-xs" />
          <div className="h-0.5 w-1/2 bg-ink-200 dark:bg-ink-700 rounded-xs" />
        </div>
      </div>
    )
  }

  // classic-one-page (default)
  return (
    <div className={cn('w-10 h-13 rounded-xs border bg-white dark:bg-ink-50 shrink-0 p-1', borderColor)}>
      <div className="space-y-0.5">
        <div className="h-0.5 w-3/4 bg-ink-300 dark:bg-ink-600 rounded-xs mx-auto" />
        <div className="h-0.5 w-1/3 bg-ink-200 dark:bg-ink-700 rounded-xs mx-auto" />
        <div className="h-px bg-ink-200 dark:bg-ink-700 my-0.5" />
        <div className="h-0.5 w-2/3 bg-ink-200 dark:bg-ink-700 rounded-xs mx-auto" />
        <div className="h-0.5 w-3/4 bg-ink-200 dark:bg-ink-700 rounded-xs" />
        <div className="h-0.5 w-2/3 bg-ink-200 dark:bg-ink-700 rounded-xs" />
        <div className="h-0.5 w-1/2 bg-ink-200 dark:bg-ink-700 rounded-xs" />
      </div>
    </div>
  )
}

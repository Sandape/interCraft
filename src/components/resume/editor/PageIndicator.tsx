/**
 * Page indicator + single/multi-page mode toggle.
 *
 * Shows "1/2 页" (page count) and a button to switch between single-page
 * (clip to first A4 page) and multi-page (show all) modes.
 */
import { useState } from 'react'
import { FileText, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PageIndicatorProps {
  pageCount: number
  /** Controlled single-page mode flag. If undefined, component manages its own state. */
  singlePageMode?: boolean
  onSinglePageModeChange?: (enabled: boolean) => void
  className?: string
}

export default function PageIndicator({
  pageCount,
  singlePageMode: controlledMode,
  onSinglePageModeChange,
  className = '',
}: PageIndicatorProps) {
  const [internalMode, setInternalMode] = useState(false)
  const singlePageMode = controlledMode ?? internalMode

  function toggleMode() {
    const next = !singlePageMode
    if (onSinglePageModeChange) {
      onSinglePageModeChange(next)
    } else {
      setInternalMode(next)
    }
  }

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-2.5 py-1 rounded-md bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border shadow-sm',
        className,
      )}
      data-testid="page-indicator"
    >
      <span className="text-2xs font-medium text-ink-2 tabular-nums">
        {pageCount} 页
      </span>
      <button
        onClick={toggleMode}
        className={cn(
          'flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs transition-colors',
          singlePageMode
            ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300'
            : 'text-ink-3 hover:text-ink-1 hover:bg-surface-muted',
        )}
        aria-label={singlePageMode ? '切换到多页模式' : '切换到单页模式'}
        data-testid="page-mode-toggle"
        title={singlePageMode ? '当前：单页模式（只显示第一页）' : '当前：多页模式（显示所有页）'}
      >
        {singlePageMode ? <FileText className="h-3 w-3" /> : <Layers className="h-3 w-3" />}
        {singlePageMode ? '单页' : '多页'}
      </button>
    </div>
  )
}

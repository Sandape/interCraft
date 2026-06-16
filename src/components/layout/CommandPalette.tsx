/**
 * CommandPalette — global search command palette.
 *
 * Mounted once from AppShell. Driven by the useGlobalSearch hook.
 * Handles all four user stories:
 *   US1: open / type / click result
 *   US2: keyboard navigation (ArrowUp/Down/Enter/Escape)
 *   US3: empty hint / loading / no-results / error states
 *   US4: outside-click close; previously-focused element is restored
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, X, Loader2, FileText, MessageSquareText, Radar, BookOpen, GraduationCap } from 'lucide-react'
import { useGlobalSearch } from '@/hooks/queries/useGlobalSearch'
import { cn } from '@/lib/utils'
import type { SearchGroup, SearchResultItem, SearchType } from '@/types/search'

const TYPE_ICON: Record<SearchType, React.ReactNode> = {
  resume: <FileText className="h-3.5 w-3.5" />,
  interview: <MessageSquareText className="h-3.5 w-3.5" />,
  ability: <Radar className="h-3.5 w-3.5" />,
  faq: <BookOpen className="h-3.5 w-3.5" />,
  resource: <GraduationCap className="h-3.5 w-3.5" />,
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { query, setQuery, groups, requestState, error, retry } = useGlobalSearch()
  const [highlight, setHighlight] = useState(0)
  const panelRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)

  // Flatten groups into a single ordered list for keyboard navigation.
  const flatResults: SearchResultItem[] = useMemo(() => {
    const out: SearchResultItem[] = []
    for (const g of groups) {
      for (const item of g.items) out.push(item)
    }
    return out
  }, [groups])

  // When groups change, reset the highlight.
  useEffect(() => {
    setHighlight(0)
  }, [groups])

  // Focus the input when opened, restore previous focus when closed.
  useEffect(() => {
    if (open) {
      previouslyFocusedRef.current = (document.activeElement as HTMLElement) ?? null
      // Defer to next tick so the input is mounted.
      const t = setTimeout(() => inputRef.current?.focus(), 0)
      return () => clearTimeout(t)
    } else {
      // Restore focus
      const prev = previouslyFocusedRef.current
      if (prev && typeof prev.focus === 'function') {
        prev.focus()
      }
      previouslyFocusedRef.current = null
      setQuery('')
      setHighlight(0)
    }
  }, [open, setQuery])

  // Outside click closes the palette.
  useEffect(() => {
    if (!open) return
    function handlePointerDown(event: MouseEvent) {
      if (!panelRef.current) return
      if (panelRef.current.contains(event.target as Node)) return
      onClose()
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [open, onClose])

  // Keyboard navigation.
  useEffect(() => {
    if (!open) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (flatResults.length === 0) return
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setHighlight((h) => (h + 1) % flatResults.length)
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        setHighlight((h) => (h - 1 + flatResults.length) % flatResults.length)
      } else if (event.key === 'Enter') {
        event.preventDefault()
        const target = flatResults[highlight]
        if (target) {
          onClose()
          navigate(target.destination)
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, flatResults, highlight, navigate, onClose])

  useEffect(() => {
    if (!open || flatResults.length === 0) return
    const selected = panelRef.current?.querySelector<HTMLElement>('[aria-selected="true"]')
    selected?.scrollIntoView({ block: 'nearest' })
  }, [open, flatResults, highlight])

  if (!open) return null

  const hasQuery = query.trim().length > 0
  const isEmpty = requestState === 'idle' && !hasQuery
  const isLoading = requestState === 'loading'
  const isError = requestState === 'error'
  const isNoResults =
    requestState === 'success' && hasQuery && flatResults.length === 0
  const showResults = requestState === 'success' && flatResults.length > 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] px-4 bg-black/30 dark:bg-black/50 backdrop-blur-sm animate-fade-in"
      data-testid="command-palette-overlay"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="全局搜索"
        data-testid="command-palette"
        className="w-full max-w-xl surface-1 rounded-lg border border-surface-border dark:border-dark-surface-border shadow-notion-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 h-11 border-b border-surface-border dark:border-dark-surface-border">
          <Search className="h-4 w-4 text-ink-3 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索简历、面试记录、能力维度…"
            className="flex-1 h-full bg-transparent text-sm text-ink-1 placeholder:text-ink-muted focus:outline-none"
            data-testid="command-palette-input"
            autoComplete="off"
            spellCheck={false}
          />
          {isLoading && (
            <Loader2
              className="h-4 w-4 text-ink-3 animate-spin"
              data-testid="command-palette-loading"
            />
          )}
          <button
            type="button"
            onClick={onClose}
            className="h-6 w-6 inline-flex items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary"
            aria-label="关闭"
            data-testid="command-palette-close"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div
          className="max-h-[60vh] overflow-y-auto"
          data-testid="command-palette-body"
        >
          {isEmpty && (
            <div
              className="px-4 py-6 text-sm text-ink-3"
              data-testid="command-palette-empty-hint"
            >
              支持搜索简历分支、面试记录、能力维度、常见问题、学习资源。按
              <kbd className="mx-1 px-1 py-0.5 rounded bg-surface-muted dark:bg-dark-surface-muted text-2xs">Esc</kbd>
              关闭。
            </div>
          )}

          {isNoResults && (
            <div
              className="px-4 py-6 text-sm text-ink-3"
              data-testid="command-palette-no-results"
            >
              未找到与「{query.trim()}」匹配的结果。
            </div>
          )}

          {isError && (
            <div
              className="px-4 py-4 text-sm"
              data-testid="command-palette-error"
            >
              <div className="text-red-600 dark:text-red-400">{error ?? '搜索失败'}</div>
              <button
                type="button"
                onClick={retry}
                data-testid="command-palette-retry"
                className="mt-2 text-xs text-brand-600 dark:text-brand-300 hover:underline"
              >
                重试
              </button>
            </div>
          )}

          {showResults && (
            <ul role="listbox" className="py-1">
              {groups.map((group) => (
                <li key={group.type} data-testid={`command-palette-group-${group.type}`}>
                  <div className="px-3 pt-2 pb-1 text-2xs font-semibold text-ink-3 uppercase tracking-wider">
                    {group.label}
                  </div>
                  <ul>
                    {group.items.map((item) => {
                      const flatIndex = flatResults.findIndex((r) => r.id === item.id && r.type === item.type)
                      const selected = flatIndex === highlight
                      return (
                        <li key={`${item.type}:${item.id}`} role="presentation">
                          <button
                            type="button"
                            role="option"
                            aria-selected={selected}
                            data-testid={`command-palette-result-${item.id}`}
                            onMouseEnter={() => setHighlight(flatIndex)}
                            onClick={() => {
                              onClose()
                              navigate(item.destination)
                            }}
                            className={cn(
                              'w-full flex items-center gap-2.5 px-3 py-1.5 text-left text-sm transition-colors',
                              selected
                                ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300'
                                : 'text-ink-1 hover:bg-surface-muted dark:hover:bg-dark-surface-muted',
                            )}
                          >
                            <span
                              className={cn(
                                'h-6 w-6 rounded-md inline-flex items-center justify-center flex-shrink-0',
                                selected
                                  ? 'bg-white/60 dark:bg-white/5'
                                  : 'bg-surface-muted dark:bg-dark-surface-muted text-ink-3',
                              )}
                            >
                              {TYPE_ICON[item.type]}
                            </span>
                            <span className="flex-1 min-w-0">
                              <span className="block truncate">{item.title}</span>
                              {item.subtitle && (
                                <span className="block text-2xs text-ink-3 truncate">
                                  {item.subtitle}
                                </span>
                              )}
                            </span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="px-3 h-8 border-t border-surface-border dark:border-dark-surface-border flex items-center justify-between text-2xs text-ink-3">
          <span>
            <kbd className="px-1 py-0.5 rounded bg-surface-muted dark:bg-dark-surface-muted">↑↓</kbd>
            <span className="ml-1">移动</span>
            <kbd className="ml-2 px-1 py-0.5 rounded bg-surface-muted dark:bg-dark-surface-muted">Enter</kbd>
            <span className="ml-1">打开</span>
            <kbd className="ml-2 px-1 py-0.5 rounded bg-surface-muted dark:bg-dark-surface-muted">Esc</kbd>
            <span className="ml-1">关闭</span>
          </span>
          <span>InterCraft 搜索</span>
        </div>
      </div>
    </div>
  )
}

export default CommandPalette

// Exported for tests that need to assert against the empty groups filter.
export const _internals = { TYPE_ICON }

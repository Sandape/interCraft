/**
 * LogCenter command palette — REQ-039 B2 US1 (⌘K).
 *
 * Two lists: Recent (last 5 unique trace_ids the page has loaded) +
 * Filters (one-click apply each filter preset). Esc / ⌘K closes.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { AdminFilters } from '@/types/admin-console'

interface Props {
  open: boolean
  onClose: () => void
  recentTaskIds: string[]
  filters: AdminFilters
  onApplyFilters: (next: Partial<AdminFilters>) => void
}

interface PaletteItem {
  label: string
  meta?: string
  run: () => void
  group: 'recent' | 'filter'
}

export function LogCenterCommandPalette(props: Props): ReactNode {
  const { open, onClose, recentTaskIds, filters, onApplyFilters } = props
  const [query, setQuery] = useState('')
  const [activeIdx, setActiveIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      setActiveIdx(0)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const items = useMemo<PaletteItem[]>(() => {
    const out: PaletteItem[] = []
    for (const id of recentTaskIds.slice(0, 5)) {
      out.push({
        label: `打开 trace ${id.slice(0, 8)}…`,
        meta: id,
        group: 'recent',
        run: () => {
          // navigate via URL search params; the page is responsible for
          // actually loading the trace, so we just close.
          onApplyFilters({ search: id })
          onClose()
        },
      })
    }
    const presets: Array<{ label: string; patch: Partial<AdminFilters> }> = [
      { label: '显示最近 24 小时', patch: { since: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString() } },
      { label: '只看失败任务', patch: { status: 'failed' } },
      { label: '只看 success', patch: { status: 'success' } },
      { label: '只看 interview 类型', patch: { task_type: 'interview' } },
      { label: '只看 resume_optimize 类型', patch: { task_type: 'resume_optimize' } },
      { label: '清除全部筛选', patch: { since: '', status: '', task_type: '', search: '' } },
    ]
    for (const p of presets) {
      out.push({
        label: p.label,
        group: 'filter',
        run: () => {
          onApplyFilters(p.patch)
          onClose()
        },
      })
    }
    return out
  }, [recentTaskIds, onApplyFilters, onClose])

  const filtered = useMemo(() => {
    if (!query) return items
    const q = query.toLowerCase()
    return items.filter(
      (it) =>
        it.label.toLowerCase().includes(q) || (it.meta ?? '').toLowerCase().includes(q),
    )
  }, [items, query])

  if (!open) return null

  return (
    <div
      className="ac-palette-overlay"
      onClick={onClose}
      data-testid="command-palette-overlay"
    >
      <div
        className="ac-palette"
        onClick={(e) => e.stopPropagation()}
        data-testid="command-palette"
      >
        <input
          ref={inputRef}
          className="ac-palette__input"
          placeholder="搜索任务或筛选…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActiveIdx(0)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setActiveIdx((i) => Math.min(i + 1, filtered.length - 1))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActiveIdx((i) => Math.max(0, i - 1))
            } else if (e.key === 'Enter') {
              e.preventDefault()
              filtered[activeIdx]?.run()
            }
          }}
        />
        <div className="ac-palette__list">
          {filtered.length === 0 ? (
            <div className="ac-palette__item">无匹配命令</div>
          ) : (
            filtered.map((it, idx) => (
              <div
                key={`${it.group}-${idx}`}
                className={
                  idx === activeIdx
                    ? 'ac-palette__item ac-palette__item--active'
                    : 'ac-palette__item'
                }
                onClick={it.run}
                data-testid="palette-item"
              >
                <span>{it.label}</span>
                {it.meta && <span className="ac-palette__item-meta">{it.meta}</span>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * ResumeListToolbar — search + status multi-select + sort dropdown.
 * US6 T084.
 */
import { useEffect, useState } from 'react'
import { Search, ChevronDown, X, ArrowUpDown } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import type { BranchStatus } from '@/modules/resume/api/types'

export type SortKey = 'edited' | 'created' | 'match_score'

export interface ResumeListToolbarProps {
  search: string
  onSearchChange: (v: string) => void
  statusFilter: BranchStatus[]
  onStatusFilterChange: (s: BranchStatus[]) => void
  sort: SortKey
  onSortChange: (s: SortKey) => void
  resultCount?: number
}

const STATUS_OPTIONS: { value: BranchStatus; label: string }[] = [
  { value: 'draft', label: '草稿' },
  { value: 'optimizing', label: '优化中' },
  { value: 'ready', label: '就绪' },
  { value: 'submitted', label: '已投递' },
  { value: 'archived', label: '归档' },
]

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'edited', label: '最近编辑' },
  { value: 'created', label: '最近创建' },
  { value: 'match_score', label: '匹配度' },
]

export default function ResumeListToolbar({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  sort,
  onSortChange,
  resultCount,
}: ResumeListToolbarProps) {
  const [statusOpen, setStatusOpen] = useState(false)
  const [debouncedSearch, setDebouncedSearch] = useState(search)

  // 027 US6: debounced 200ms search
  useEffect(() => {
    const t = setTimeout(() => onSearchChange(debouncedSearch), 200)
    return () => clearTimeout(t)
  }, [debouncedSearch, onSearchChange])

  useEffect(() => {
    setDebouncedSearch(search)
  }, [search])

  function toggleStatus(s: BranchStatus) {
    if (statusFilter.includes(s)) {
      onStatusFilterChange(statusFilter.filter((x) => x !== s))
    } else {
      onStatusFilterChange([...statusFilter, s])
    }
  }

  return (
    <div className="flex items-center gap-2 mb-4" data-testid="resume-list-toolbar">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-3 pointer-events-none" />
        <Input
          value={debouncedSearch}
          onChange={(e) => setDebouncedSearch(e.target.value)}
          placeholder="搜索分支名称 / 公司 / 职位"
          className="pl-8"
          data-testid="resume-list-search"
        />
        {debouncedSearch && (
          <button
            onClick={() => {
              setDebouncedSearch('')
              onSearchChange('')
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink-1"
            aria-label="清除搜索"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Status multi-select */}
      <div className="relative">
        <button
          onClick={() => setStatusOpen((v) => !v)}
          className="h-9 px-3 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1 flex items-center gap-1.5 hover:bg-surface-muted dark:hover:bg-dark-surface-muted"
          data-testid="resume-list-status-toggle"
        >
          <span>状态</span>
          {statusFilter.length > 0 && (
            <span className="text-2xs font-medium text-brand-600 bg-brand-50 dark:bg-brand-500/20 dark:text-brand-300 px-1.5 py-0.5 rounded">
              {statusFilter.length}
            </span>
          )}
          <ChevronDown className="h-3 w-3" />
        </button>
        {statusOpen && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setStatusOpen(false)}
            />
            <div
              className="absolute top-full mt-1 left-0 z-20 min-w-40 rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface shadow-lg py-1"
              data-testid="resume-list-status-menu"
            >
              {STATUS_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-surface-muted dark:hover:bg-dark-surface-muted cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={statusFilter.includes(opt.value)}
                    onChange={() => toggleStatus(opt.value)}
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
              {statusFilter.length > 0 && (
                <button
                  onClick={() => {
                    onStatusFilterChange([])
                    setStatusOpen(false)
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs text-ink-3 hover:bg-surface-muted dark:hover:bg-dark-surface-muted border-t border-surface-border dark:border-dark-surface-border"
                >
                  清除筛选
                </button>
              )}
            </div>
          </>
        )}
      </div>

      {/* Sort dropdown */}
      <div className="relative">
        <select
          value={sort}
          onChange={(e) => onSortChange(e.target.value as SortKey)}
          className="h-9 pl-8 pr-7 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1 appearance-none"
          data-testid="resume-list-sort"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ArrowUpDown className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-ink-3 pointer-events-none" />
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-ink-3 pointer-events-none" />
      </div>

      {resultCount !== undefined && (
        <span className="text-2xs text-ink-3 whitespace-nowrap">
          {resultCount} 个分支
        </span>
      )}
    </div>
  )
}

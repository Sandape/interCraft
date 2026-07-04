/**
 * Logs/Traces filter bar — REQ-039 B2 US1.
 *
 * Four dimensions: time range / task type / status / keyword search.
 * Mutating any filter fires a refresh via the `onChange` callback
 * (the page is responsible for URL-syncing + refetch via TanStack).
 */
import { useMemo } from 'react'
import type { AdminFilters, NormalizedStatus, NormalizedTaskType } from '@/types/admin-console'

interface Props {
  filters: AdminFilters
  onChange: (next: AdminFilters) => void
  onRefresh: () => void
  refreshing: boolean
}

const TIME_RANGES = [
  { value: '1h', label: '最近 1 小时' },
  { value: '24h', label: '最近 24 小时' },
  { value: '7d', label: '最近 7 天' },
  { value: 'all', label: '全部' },
]

const TASK_TYPES: Array<{ value: '' | NormalizedTaskType; label: string }> = [
  { value: '', label: '全部类型' },
  { value: 'interview', label: 'interview' },
  { value: 'resume_optimize', label: 'resume_optimize' },
  { value: 'ability_diagnose', label: 'ability_diagnose' },
  { value: 'error_coach', label: 'error_coach' },
  { value: 'general_coach', label: 'general_coach' },
  { value: 'unknown', label: 'unknown' },
]

const STATUS_OPTIONS: Array<{ value: '' | NormalizedStatus; label: string }> = [
  { value: '', label: '全部状态' },
  { value: 'success', label: 'success' },
  { value: 'failed', label: 'failed' },
  { value: 'pending', label: 'pending' },
  { value: 'running', label: 'running' },
]

export function rangeToSince(value: string): string {
  if (!value || value === 'all') return ''
  const now = Date.now()
  const map: Record<string, number> = {
    '1h': 60 * 60 * 1000,
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
  }
  return new Date(now - (map[value] ?? map['24h'])).toISOString()
}

export function LogCenterFilterBar({
  filters,
  onChange,
  onRefresh,
  refreshing,
}: Props) {
  const since = useMemo(() => filters.since, [filters.since])

  return (
    <div className="ac-filter-bar" role="search">
      <div className="ac-filter-bar__field">
        <label>时间</label>
        <select
          value={
            since
              ? '24h'
              : 'all'
          }
          onChange={(e) => {
            const next = e.target.value
            onChange({
              ...filters,
              since: rangeToSince(next),
            })
          }}
          data-testid="filter-time"
        >
          {TIME_RANGES.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      <div className="ac-filter-bar__field">
        <label>类型</label>
        <select
          value={filters.task_type}
          onChange={(e) =>
            onChange({ ...filters, task_type: e.target.value })
          }
          data-testid="filter-task-type"
        >
          {TASK_TYPES.map((opt) => (
            <option key={opt.value || 'all'} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      <div className="ac-filter-bar__field">
        <label>状态</label>
        <select
          value={filters.status}
          onChange={(e) =>
            onChange({ ...filters, status: e.target.value })
          }
          data-testid="filter-status"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value || 'all'} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      <div className="ac-filter-bar__field">
        <label>搜索</label>
        <input
          type="search"
          placeholder="trace_id / 错误关键词"
          value={filters.search}
          onChange={(e) =>
            onChange({ ...filters, search: e.target.value })
          }
          data-testid="filter-search"
        />
      </div>
      <div className="ac-filter-bar__field" style={{ gridColumn: '1 / -1', justifyContent: 'flex-end', flexDirection: 'row', display: 'flex' }}>
        <button
          type="button"
          className="ac-btn ac-btn--primary"
          onClick={onRefresh}
          disabled={refreshing}
          data-testid="filter-refresh"
        >
          {refreshing ? <span className="spinner" /> : null}
          {refreshing ? '正在刷新…' : 'Refresh'}
        </button>
      </div>
    </div>
  )
}

/**
 * LogCenter task list — REQ-039 B2 US1.
 *
 * Columns: task_id / type / status / started_at / duration / Replay btn / Diff checkbox
 *
 * Row click selects the trace (passed to detail panel).
 * Diff checkbox supports multi-select up to 2 (open DiffDialog when 2 picked).
 * Replay button visible only when caller holds REPLAY_TRIGGER capability.
 */
import { useMemo, useState, type ReactNode } from 'react'
import { Loader2, RotateCcw } from 'lucide-react'
import type { AdminTrace } from '@/types/admin-console'
import {
  buildGanttFromTrace,
  formatDuration,
  microGantt,
  normalizeStatus,
  normalizeType,
  shortId,
} from './index'

interface Props {
  traces: AdminTrace[]
  loading: boolean
  selectedTraceId: string | null
  onSelect: (traceId: string) => void
  onReplay: (traceId: string) => void
  replayingFor: string | null
  capabilities: string[]
  searchKeyword: string
  // Micro-gantt inputs come from the same trace; we synthesize one
  // even when the detail panel hasn't loaded the node tree yet.
  nodeSpans?: Record<string, Array<{ id: string; label: string; startMs: number; endMs: number; status: 'success' | 'failed' | 'pending' | 'running' }>>
  // Diff multi-select
  diffSelection: string[]
  onToggleDiffSelection: (traceId: string) => void
  onOpenDiff: () => void
  // Tag chips per row (so the list shows the caller's private tags inline)
  tagsByTask: Record<string, string[]>
  onOpenTags: (taskId: string) => void
}

function isHttpishUuid(id: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)
}

export function LogCenterTaskList(props: Props): ReactNode {
  const {
    traces,
    loading,
    selectedTraceId,
    onSelect,
    onReplay,
    replayingFor,
    capabilities,
    searchKeyword,
    nodeSpans,
    diffSelection,
    onToggleDiffSelection,
    onOpenDiff,
    tagsByTask,
    onOpenTags,
  } = props

  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const filtered = useMemo(() => {
    if (!searchKeyword) return traces
    const kw = searchKeyword.toLowerCase()
    return traces.filter(
      (t) =>
        t.id.toLowerCase().includes(kw) ||
        (t.error_message ?? '').toLowerCase().includes(kw) ||
        t.task_type.toLowerCase().includes(kw),
    )
  }, [traces, searchKeyword])

  const hasReplayCapability = capabilities.includes('REPLAY_TRIGGER')

  if (loading && traces.length === 0) {
    return (
      <div className="ac-loading" data-testid="task-list-loading">
        <Loader2 size={14} /> 正在载入任务列表…
      </div>
    )
  }

  if (!loading && filtered.length === 0) {
    return (
      <div className="ac-empty" data-testid="task-list-empty">
        没有匹配的任务。点击 Refresh 或调整筛选条件。
      </div>
    )
  }

  return (
    <>
      {diffSelection.length > 0 && (
        <div
          style={{
            padding: '6px 10px',
            background: 'rgba(56, 189, 248, 0.08)',
            borderBottom: '1px solid var(--ac-border-subtle)',
            fontSize: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          已选择 <span className="ac-mono">{diffSelection.length}/2</span> 条 trace
          {diffSelection.length === 2 && (
            <button
              type="button"
              className="ac-btn ac-btn--primary"
              onClick={onOpenDiff}
              data-testid="open-diff"
            >
              对比 Diff
            </button>
          )}
          <button
            type="button"
            className="ac-btn ac-btn--ghost"
            onClick={() => {
              diffSelection.forEach((id) => onToggleDiffSelection(id))
            }}
            data-testid="clear-diff"
          >
            清除
          </button>
        </div>
      )}

      <div className="ac-task-list">
        <table className="ac-task-table" data-testid="task-table">
          <thead>
            <tr>
              <th className="ac-task-table__checkbox">Diff</th>
              <th>任务 ID</th>
              <th>类型</th>
              <th>状态</th>
              <th>开始</th>
              <th>耗时</th>
              <th>标签</th>
              <th>时间线</th>
              <th style={{ width: 92 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((trace) => {
              const status = normalizeStatus(trace.status)
              const typeName = normalizeType(trace.task_type)
              const tags = tagsByTask[trace.id] ?? []
              const isActive = trace.id === selectedTraceId
              const isChecked = diffSelection.includes(trace.id)
              const canReplay =
                hasReplayCapability &&
                trace.status !== 'success' &&
                Boolean(trace.task_id ?? trace.id)
              const spans =
                nodeSpans?.[trace.id] ?? buildGanttFromTrace(trace, [])
              const replaying = replayingFor === trace.id
              return (
                <tr
                  key={trace.id}
                  className={isActive ? 'ac-task-table__row--active' : undefined}
                  onClick={() => onSelect(trace.id)}
                  data-testid="task-row"
                >
                  <td
                    className="ac-task-table__checkbox"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => onToggleDiffSelection(trace.id)}
                      aria-label={`select-${trace.id}`}
                      disabled={
                        !isChecked && diffSelection.length >= 2
                      }
                      data-testid="task-diff-checkbox"
                    />
                  </td>
                  <td>
                    <div className="ac-task-table__id">{shortId(trace.id, 8)}</div>
                    {trace.replay_of ? (
                      <span className="ac-replay-badge" title={trace.replay_of}>
                        Replay of {shortId(trace.replay_of, 8)}
                      </span>
                    ) : null}
                    {isHttpishUuid(trace.id) && (
                      <div style={{ color: 'var(--ac-ink-faint)', fontSize: 10, marginTop: 2 }}>
                        {trace.id}
                      </div>
                    )}
                  </td>
                  <td className="ac-mono" style={{ fontSize: 11 }}>{typeName}</td>
                  <td>
                    <span className={`ac-status ac-status--${status}`}>{status}</span>
                    {trace.error_message && (
                      <div
                        style={{
                          color: 'var(--ac-failed)',
                          fontSize: 11,
                          marginTop: 4,
                          maxWidth: 220,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                        title={trace.error_message}
                      >
                        {trace.error_message}
                      </div>
                    )}
                  </td>
                  <td className="ac-mono" style={{ fontSize: 11 }}>
                    {trace.started_at
                      ? new Date(trace.started_at).toLocaleString('zh-CN', { hour12: false })
                      : '—'}
                  </td>
                  <td className="ac-mono" style={{ fontSize: 11 }}>
                    {formatDuration(trace.duration_ms)}
                  </td>
                  <td>
                    {tags.length === 0 ? (
                      <span style={{ color: 'var(--ac-ink-faint)', fontSize: 11 }}>—</span>
                    ) : (
                      tags.map((t) => (
                        <span
                          key={t}
                          className={`ac-tag-chip ac-tag-chip--${tagPresetClass(t)}`}
                        >
                          {t}
                        </span>
                      ))
                    )}
                    <div>
                      <button
                        type="button"
                        className="ac-btn ac-btn--ghost"
                        style={{ fontSize: 10, padding: '1px 6px' }}
                        onClick={(e) => {
                          e.stopPropagation()
                          onOpenTags(trace.id)
                        }}
                        data-testid="open-tags"
                      >
                        + 标签
                      </button>
                    </div>
                  </td>
                  <td>
                    <div onClick={(e) => e.stopPropagation()}>
                      {spans.length > 0 ? (
                        <div
                          onClick={(e) => {
                            e.stopPropagation()
                            setExpanded((s) => ({ ...s, [trace.id]: !s[trace.id] }))
                          }}
                          style={{ cursor: 'pointer' }}
                        >
                          {microGantt(spans)}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--ac-ink-faint)', fontSize: 10 }}>
                          click to load
                        </span>
                      )}
                    </div>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {canReplay ? (
                      <button
                        type="button"
                        className="ac-btn"
                        onClick={() => onReplay(trace.id)}
                        disabled={replaying}
                        data-testid="replay-btn"
                        title="Replay 后端将创建一个新的 trace"
                      >
                        {replaying ? <span className="spinner" /> : <RotateCcw size={12} />}
                        Replay
                      </button>
                    ) : (
                      <span
                        className="ac-mono"
                        style={{ color: 'var(--ac-ink-faint)', fontSize: 10 }}
                        title={
                          hasReplayCapability
                            ? '该任务状态不允许 Replay'
                            : '需要 REPLAY_TRIGGER 权限'
                        }
                      >
                        {hasReplayCapability ? '—' : '🔒 Replay'}
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

function tagPresetClass(tag: string): string {
  switch (tag) {
    case 'needs-fix':
      return 'needs-fix'
    case 'intermittent-flake':
      return 'intermittent-flake'
    case 'customer-escalation':
      return 'customer-escalation'
    case 'p1-incident':
      return 'p1-incident'
    case 'monitoring':
      return 'monitoring'
    default:
      return 'monitoring'
  }
}

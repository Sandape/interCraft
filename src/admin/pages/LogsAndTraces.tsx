/**
 * LogsAndTraces — REQ-044 FR-005 + US5 / FR-024 + FR-025 + FR-026.
 *
 * Workspace page that wraps the existing LogCenter business logic
 * (REQ-039 B2) under the new 8-workspace IA shell, and adds the
 * US5 drilldown surface:
 *
 * - Drilldown banner (?from=incident|signal|badcase|user|trace:id)
 * - Tabs for "Logs" / "Traces" / "List" (legacy)
 * - Log list / trace list filtered by correlation_id when drilled in
 * - Coverage gap notice when no correlated log/trace exists
 * - LogDetailDrawer (4-panel deep view + masked sensitive + reveal)
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { LogCenter as _BaseLogsAndTraces } from './LogCenter'
import { DrilldownBanner } from '@/admin/components/log/DrilldownBanner'
import { CoverageGapNotice } from '@/admin/components/log/CoverageGapNotice'
import { LogDetailDrawer } from '@/admin/components/log/LogDetailDrawer'
import { adminLogsApi, parseDrilldownParam } from '@/api/admin-logs'
import type { DrilldownSource, LogEvent } from '@/types/admin-logs'

type TabId = 'logs' | 'traces' | 'list' | 'tasks'

const TAB_LABELS: Record<TabId, string> = {
  logs: '日志',
  traces: '链路',
  list: '链路列表',
  tasks: '任务检查',
}

export function LogsAndTraces() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState<TabId>('logs')
  const [selectedLog, setSelectedLog] = useState<LogEvent | null>(null)

  // FR-024 — parse ?from=source_type:source_id
  const drilldown: DrilldownSource | null = useMemo(() => {
    const from = searchParams.get('from')
    return parseDrilldownParam(from)
  }, [searchParams])

  const traceIdFromUrl = searchParams.get('trace')

  // FR-024 — auto-load log events correlated with the drilldown source.
  const logsQuery = useCallback(async () => {
    if (!drilldown) {
      return { events: [] as LogEvent[], total: 0, coverageGap: false }
    }
    return adminLogsApi.listLogEvents({ from: drilldown, traceId: traceIdFromUrl })
  }, [drilldown, traceIdFromUrl])

  // We keep the data fetch state local rather than via TanStack to
  // keep US5 scope minimal and avoid cross-cutting cache invalidation.
  const [logs, setLogs] = useState<LogEvent[]>([])
  const [logsTotal, setLogsTotal] = useState(0)
  const [coverageGap, setCoverageGap] = useState(false)
  const [logsLoading, setLogsLoading] = useState(false)

  useEffect(() => {
    if (!drilldown) {
      setLogs([])
      setLogsTotal(0)
      setCoverageGap(false)
      return
    }
    let canceled = false
    setLogsLoading(true)
    logsQuery()
      .then((res) => {
        if (canceled) return
        setLogs(res.events)
        setLogsTotal(res.total)
        setCoverageGap(res.coverageGap)
      })
      .catch(() => {
        if (canceled) return
        setLogs([])
        setLogsTotal(0)
        setCoverageGap(false)
      })
      .finally(() => {
        if (!canceled) setLogsLoading(false)
      })
    return () => {
      canceled = true
    }
  }, [drilldown, logsQuery])

  // AC-24.3 — when source is a trace, auto-select it.
  const autoSelectTraceId =
    drilldown?.type === 'trace' ? drilldown.id : traceIdFromUrl

  const handleAutoSelectTrace = useCallback(
    (traceId: string) => {
      const next = new URLSearchParams(searchParams)
      next.set('trace', traceId)
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  // When in "list" mode (no drilldown), delegate to the legacy
  // LogCenter page so all existing US1 functionality (filter, replay,
  // diff, tag, command palette) stays reachable.
  if (!drilldown) {
    return <_BaseLogsAndTraces />
  }

  return (
    <div className="ac-page" data-testid="logs-and-traces-drilldown">
      <div className="ac-page__header">
        <h1 className="ac-page__title">日志与链路</h1>
        <span className="ac-page__hint">
          运维下钻 · 日志检索与链路追踪
        </span>
      </div>

      <DrilldownBanner
        source={drilldown}
        onAutoSelectTrace={handleAutoSelectTrace}
        autoSelectTraceId={autoSelectTraceId}
      />

      <nav
        className="ac-lt-tabs"
        role="tablist"
        aria-label="Logs & Traces tabs"
      >
        {(Object.keys(TAB_LABELS) as TabId[]).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={`ac-lt-tab ${tab === id ? 'is-active' : ''}`}
            data-testid={`logs-traces-tab-${id}`}
            aria-selected={tab === id}
            onClick={() => setTab(id)}
          >
            {TAB_LABELS[id]}
          </button>
        ))}
      </nav>

      <div className="ac-lt-tabpanel" data-testid="logs-traces-tabpanel">
        {tab === 'logs' ? (
          <LogsTab
            loading={logsLoading}
            logs={logs}
            total={logsTotal}
            coverageGap={coverageGap}
            sourceType={drilldown.type}
            sourceId={drilldown.id}
            onSelectLog={setSelectedLog}
          />
        ) : null}

        {tab === 'traces' ? (
          <TracesTab source={drilldown} />
        ) : null}

        {tab === 'list' ? (
          <_BaseLogsAndTraces />
        ) : null}

        {tab === 'tasks' ? <TaskInspectionPanel /> : null}
      </div>

      <LogDetailDrawer
        open={Boolean(selectedLog)}
        log={selectedLog}
        onClose={() => setSelectedLog(null)}
      />
    </div>
  )
}

interface LogsTabProps {
  loading: boolean
  logs: LogEvent[]
  total: number
  coverageGap: boolean
  sourceType: DrilldownSource['type']
  sourceId: string
  onSelectLog: (log: LogEvent) => void
}

function LogsTab({
  loading,
  logs,
  total,
  coverageGap,
  sourceType,
  sourceId,
  onSelectLog,
}: LogsTabProps) {
  if (loading) {
    return (
      <div className="ac-lt-loading" data-testid="logs-tab-loading">
        加载相关 log…
      </div>
    )
  }
  if (coverageGap || total === 0) {
    return (
      <CoverageGapNotice sourceType={sourceType} sourceId={sourceId} />
    )
  }
  return (
    <ul className="ac-lt-log-list" data-testid="logs-tab-list">
      {logs.map((log) => (
        <li
          key={log.id}
          className="ac-lt-log-item"
          data-testid={`log-item-${log.id}`}
        >
          <button
            type="button"
            className="ac-lt-log-item__btn"
            onClick={() => onSelectLog(log)}
            data-testid={`log-item-open-${log.id}`}
          >
            <span
              className={`ac-status ac-status--${
                log.level === 'error'
                  ? 'failed'
                  : log.level === 'warn'
                    ? 'pending'
                    : log.level === 'info'
                      ? 'success'
                      : 'pending'
              }`}
            >
              {log.level}
            </span>
            <span className="ac-lt-log-item__msg">{log.message}</span>
            <span className="ac-lt-log-item__time">{log.timestamp}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

interface TracesTabProps {
  source: DrilldownSource
}

function TracesTab({ source }: TracesTabProps) {
  const [spans, setSpans] = useState<{ id: string; spanName: string; durationMs: number | null; status: string }[]>([])
  const [loading, setLoading] = useState(false)
  const [gap, setGap] = useState(false)

  useEffect(() => {
    let canceled = false
    setLoading(true)
    adminLogsApi
      .listTraceSpans({
        from: source,
        traceId: source.type === 'trace' ? source.id : null,
      })
      .then((res) => {
        if (canceled) return
        setSpans(
          res.spans.map((s) => ({
            id: s.id,
            spanName: s.spanName,
            durationMs: s.durationMs,
            status: s.status,
          })),
        )
        setGap(res.coverageGap)
      })
      .catch(() => {
        if (!canceled) setGap(true)
      })
      .finally(() => {
        if (!canceled) setLoading(false)
      })
    return () => {
      canceled = true
    }
  }, [source])

  if (loading) {
    return (
      <div className="ac-lt-loading" data-testid="traces-tab-loading">
        加载相关 trace span…
      </div>
    )
  }
  if (gap || spans.length === 0) {
    return <CoverageGapNotice sourceType={source.type} sourceId={source.id} />
  }
  return (
    <ul className="ac-lt-span-list" data-testid="traces-tab-list">
      {spans.map((s) => (
        <li
          key={s.id}
          className="ac-lt-span-item"
          data-testid={`span-item-${s.id}`}
        >
          <span className="ac-lt-span-item__name">{s.spanName}</span>
          <span className="ac-mono">{s.id}</span>
          <span>{s.durationMs ?? '—'} ms</span>
          <span>{s.status}</span>
        </li>
      ))}
    </ul>
  )
}

/** REQ-061 T163 — soft task inspection surface wired to admin AI APIs. */
function TaskInspectionPanel() {
  const [searchParams] = useSearchParams()
  const taskId = searchParams.get('task_id')
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'degraded'>('idle')
  const [summary, setSummary] = useState<string>('选择 ?task_id= 查看运营任务投影')

  useEffect(() => {
    if (!taskId) {
      setStatus('idle')
      setSummary('选择 ?task_id= 查看运营任务投影')
      return
    }
    let canceled = false
    setStatus('loading')
    fetch(`/api/v1/admin-console/ai/tasks/${taskId}`, { credentials: 'include' })
      .then(async (res) => {
        if (canceled) return
        if (res.status === 404) {
          setStatus('degraded')
          setSummary('任务投影不可用或不存在')
          return
        }
        if (!res.ok) {
          setStatus('degraded')
          setSummary(`投影降级（HTTP ${res.status}）`)
          return
        }
        const body = await res.json()
        setStatus('ok')
        setSummary(
          `${body.status ?? 'unknown'} · ${body.capability_code ?? ''} / ${body.action_code ?? ''}`,
        )
      })
      .catch(() => {
        if (!canceled) {
          setStatus('degraded')
          setSummary('投影降级（网络错误）')
        }
      })
    return () => {
      canceled = true
    }
  }, [taskId])

  return (
    <div className="ac-lt-task-inspection" data-testid="task-inspection-panel">
      <div className="ac-page__hint">只读任务检查 · evidence-replay 不触发 provider/ledger</div>
      <p data-testid="task-inspection-status" data-status={status}>
        {summary}
      </p>
      {taskId ? (
        <ul className="ac-lt-task-links">
          <li>
            <a href={`/api/v1/admin-console/ai/tasks/${taskId}/timeline`}>时间线</a>
          </li>
          <li>
            <a href={`/api/v1/admin-console/ai/tasks/${taskId}/attempts`}>尝试</a>
          </li>
          <li>
            <a href={`/api/v1/admin-console/ai/tasks/${taskId}/evidence-replay`}>只读回放</a>
          </li>
          <li>
            <a href={`/api/v1/admin-console/ai/costs?task_id=${taskId}`}>成本</a>
          </li>
          <li>
            <a href={`/api/v1/admin-console/ai/badcases?task_id=${taskId}`}>差例</a>
          </li>
        </ul>
      ) : null}
    </div>
  )
}

export { LogCenter } from './LogCenter'

export default LogsAndTraces
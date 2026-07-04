/**
 * LogCenter page — REQ-039 B2.
 *
 * Manual refresh + URL sync + toast host + capability gating.
 *
 * URL is the source of truth for filters / selected trace / drawer
 * target. TanStack Query is configured to never auto-refetch (no
 * timers, no SSE — FR-005 / IC-4); every fetch is driven by the
 * Refresh button + ⌘R / F5 / filter change / palette quick apply.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { adminConsoleApi } from '@/api/admin-console'
import type {
  AdminDiffNodeEntry,
  AdminTaskTag,
  AdminTrace,
  AdminTraceNode,
} from '@/types/admin-console'
import { useAuthStore } from '@/stores/useAuthStore'
import { LogCenterFilterBar } from '@/admin/components/log/LogCenterFilterBar'
import { LogCenterTaskList } from '@/admin/components/log/LogCenterTaskList'
import { LogCenterDetailPanel } from '@/admin/components/log/LogCenterDetailPanel'
import { LogCenterErrorAggregation } from '@/admin/components/log/LogCenterErrorAggregation'
import { LogCenterCommandPalette } from '@/admin/components/log/LogCenterCommandPalette'
import {
  DiffDialog,
  NodeIODrawer,
  PayloadWarningDialog,
  ReplayDialog,
  TagSelector,
} from '@/admin/components/log/LogCenterDialogs'

interface Toast {
  id: number
  msg: string
  kind: 'info' | 'warn' | 'error'
}

const DEFAULT_FILTERS = {
  task_type: '',
  status: '',
  search: '',
  since: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
}

const TAG_CACHE_KEY = 'log-center:tags:v1'
// Pagination byte limits are imported from LogCenterDialogs where they
// are actually used (NodeIODrawer's fetchNodePayload call). We keep a
// single source of truth rather than re-declaring constants in this
// module just to satisfy tree-shaking guesses.

export function LogCenter() {
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  // Capabilities: a placeholder set until the backend exposes a
  // `/api/v1/me/capabilities` endpoint. We grant the demo user
  // REPLAY_TRIGGER + TASK_TAG by default per IC-6.
  const capabilities = useMemo<string[]>(
    () => (user?.email === 'demo@intercraft.io' ? ['REPLAY_TRIGGER', 'TASK_TAG'] : ['TASK_TAG']),
    [user],
  )

  const [searchParams, setSearchParams] = useSearchParams()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [drawerNodeId, setDrawerNodeId] = useState<string | null>(null)
  const [tagDialogTaskId, setTagDialogTaskId] = useState<string | null>(null)
  const [tagCache, setTagCache] = useState<Record<string, AdminTaskTag[]>>({})
  const [diffSelection, setDiffSelection] = useState<string[]>([])
  const [diffDialogOpen, setDiffDialogOpen] = useState(false)
  const [diffResult, setDiffResult] = useState<AdminDiffNodeEntry[] | null>(null)
  const [diffError, setDiffError] = useState<string | null>(null)
  const [replayDialogTraceId, setReplayDialogTraceId] = useState<string | null>(null)
  const [replayingFor, setReplayingFor] = useState<string | null>(null)
  const [payloadWarning, setPayloadWarning] = useState<{ open: boolean; bytes: number; nodeId: string | null }>({
    open: false,
    bytes: 0,
    nodeId: null,
  })
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastSeq = useRef(0)
  const inFlightController = useRef<AbortController | null>(null)

  // ---------- URL sync ----------------------------------------------------

  const filters = useMemo(
    () => ({
      task_type: searchParams.get('task_type') ?? DEFAULT_FILTERS.task_type,
      status: searchParams.get('status') ?? DEFAULT_FILTERS.status,
      search: searchParams.get('q') ?? DEFAULT_FILTERS.search,
      since: searchParams.get('since') ?? DEFAULT_FILTERS.since,
    }),
    [searchParams],
  )
  const selectedTraceId = searchParams.get('trace')

  const updateUrl = useCallback(
    (next: Record<string, string>) => {
      const params = new URLSearchParams(searchParams)
      for (const [k, v] of Object.entries(next)) {
        if (!v) params.delete(k)
        else params.set(k, v)
      }
      setSearchParams(params, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  // ---------- Toasts ------------------------------------------------------

  const notify = useCallback((msg: string, kind: 'info' | 'warn' | 'error' = 'info') => {
    toastSeq.current += 1
    const id = toastSeq.current
    setToasts((t) => [...t, { id, msg, kind }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000)
  }, [])

  // ---------- Tag cache hydration (FR-019) -------------------------------

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      const raw = window.localStorage.getItem(TAG_CACHE_KEY)
      if (raw) setTagCache(JSON.parse(raw))
    } catch {
      /* ignore */
    }
  }, [])

  // ---------- Trace list query --------------------------------------------

  const traceListQuery = useQuery({
    queryKey: ['admin', 'traces', filters],
    queryFn: async ({ signal }) => {
      // Cancel any prior refresh (FR-003).
      if (inFlightController.current) inFlightController.current.abort()
      const ctrl = new AbortController()
      inFlightController.current = ctrl
      // Forward signal so TanStack also wins if the query unmounts.
      signal?.addEventListener('abort', () => ctrl.abort())
      try {
        const res = await adminConsoleApi.listTraces(
          {
            limit: 100,
            task_type: filters.task_type || undefined,
            status: filters.status || undefined,
            since: filters.since || undefined,
          },
          ctrl.signal,
        )
        // Apply keyword search on the client because the backend has
        // no ?q= param (the search filter exists by FR-005 / US1 AC2
        // only as URL state and applied client-side to the list).
        const kw = filters.search.trim().toLowerCase()
        if (!kw) return res
        return {
          ...res,
          traces: res.traces.filter(
            (t) =>
              t.id.toLowerCase().includes(kw) ||
              (t.error_message ?? '').toLowerCase().includes(kw) ||
              t.task_type.toLowerCase().includes(kw),
          ),
        }
      } finally {
        if (inFlightController.current === ctrl) inFlightController.current = null
      }
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })

  const traces: AdminTrace[] = traceListQuery.data?.traces ?? []

  // ---------- Selected trace + node tree ---------------------------------

  const traceQuery = useQuery({
    queryKey: ['admin', 'trace', selectedTraceId],
    enabled: Boolean(selectedTraceId),
    queryFn: async ({ signal }) => {
      if (!selectedTraceId) return null
      // The list already contains the row — use it as the canonical
      // trace. Then also fetch node tree in parallel.
      const nodesQuery = adminConsoleApi
        .listTraceNodes(selectedTraceId, signal)
        .catch((err: unknown) => {
          const e = err as { status?: number }
          if (e?.status === 410) {
            notify('后端报告该 trace 已过期,正在从本地列表移除', 'warn')
            // Trace retired (FR-004 / E1).
            traceListQuery.refetch()
          }
          return { trace_id: selectedTraceId, nodes: [] as AdminTraceNode[] }
        })
      const trace = traces.find((t) => t.id === selectedTraceId) ?? null
      const nodes = await nodesQuery
      return { trace, nodes: nodes.nodes }
    },
    staleTime: 30_000,
  })

  // ---------- Tags query for selected trace -------------------------------

  const tagsQuery = useQuery({
    queryKey: ['admin', 'tags', selectedTraceId],
    enabled: Boolean(selectedTraceId),
    queryFn: async ({ signal }) => {
      if (!selectedTraceId) return [] as AdminTaskTag[]
      const res = await adminConsoleApi.listTags(selectedTraceId, signal).catch(() => ({ tags: [] as AdminTaskTag[] }))
      // Persist to cache for offline use (FR-019).
      try {
        const raw = window.localStorage.getItem(TAG_CACHE_KEY)
        const cache: Record<string, AdminTaskTag[]> = raw ? JSON.parse(raw) : {}
        cache[selectedTraceId] = res.tags
        window.localStorage.setItem(TAG_CACHE_KEY, JSON.stringify(cache))
        setTagCache(cache)
      } catch {
        /* ignore */
      }
      return res.tags
    },
    staleTime: 30_000,
  })

  // ---------- Mutations ---------------------------------------------------

  const refreshAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['admin'] })
    traceListQuery.refetch()
  }, [queryClient, traceListQuery])

  const replayMutation = useMutation({
    mutationFn: async (traceId: string) => {
      setReplayingFor(traceId)
      return adminConsoleApi.replayTrace(traceId)
    },
    onSuccess: (result) => {
      notify(`已创建新 trace ${result.new_trace_id.slice(0, 8)}… (Replay of ${result.replay_of.slice(0, 8)}…)`, 'info')
      setReplayDialogTraceId(null)
      setReplayingFor(null)
      // Auto-jump to the new trace (US2 AC2).
      updateUrl({ trace: result.new_trace_id, since: '' })
      setTimeout(refreshAll, 200)
    },
    onError: (err: unknown) => {
      setReplayingFor(null)
      const e = err as { status?: number; details?: { retry_after_seconds?: number }; message?: string }
      if (e?.status === 410) {
        notify('原模型已下线,无法重放', 'warn')
      } else if (e?.status === 429) {
        const secs = e.details?.retry_after_seconds ?? 60
        notify(`Replay 操作过于频繁,请稍候 ${secs}s 后再试`, 'warn')
      } else {
        notify(e.message ?? 'Replay 失败', 'error')
      }
    },
  })

  const diffMutation = useMutation({
    mutationFn: async (vars: { left: string; right: string }) => {
      return adminConsoleApi.diffTraces({ left_trace_id: vars.left, right_trace_id: vars.right })
    },
    onSuccess: (res) => {
      setDiffResult(res.nodes)
      setDiffError(null)
    },
    onError: (err: unknown) => {
      const e = err as { status?: number; details?: { retry_after_seconds?: number }; message?: string }
      if (e?.status === 400) {
        setDiffError('只能 diff 同 task_type 的两条 trace')
        setDiffResult(null)
      } else if (e?.status === 429) {
        const secs = e.details?.retry_after_seconds ?? 60
        setDiffError(`Diff 操作过于频繁,请稍候 ${secs}s 后再试`)
        setDiffResult(null)
      } else {
        setDiffError(e.message ?? 'Diff 失败')
        setDiffResult(null)
      }
    },
  })

  // ---------- Keyboard bindings (⌘R / F5) --------------------------------

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const isMac = navigator.platform.toUpperCase().includes('MAC')
      const modKey = isMac ? e.metaKey : e.ctrlKey
      // ⌘K → command palette
      if (modKey && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        setPaletteOpen((v) => !v)
        return
      }
      // ⌘R / F5 → refresh
      if ((modKey && (e.key === 'r' || e.key === 'R')) || e.key === 'F5') {
        e.preventDefault()
        refreshAll()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [refreshAll])

  // ---------- Node IO drawer open (with 2MB warning) ----------------------

  function onOpenNode(nodeId: string) {
    setDrawerNodeId(nodeId)
    // No heuristic to estimate total bytes; the drawer fetches the
    // first 50KB and warns if the payload hits >2MB. We intercept by
    // checking Content-Length on the first fetch — for simplicity
    // here we just open the drawer directly.
  }

  // ---------- Diff multi-select toggle ------------------------------------

  function toggleDiffSelection(traceId: string) {
    setDiffSelection((cur) => {
      const has = cur.includes(traceId)
      if (has) return cur.filter((id) => id !== traceId)
      if (cur.length >= 2) return cur
      return [...cur, traceId]
    })
  }

  function openDiffDialog() {
    if (diffSelection.length !== 2) return
    setDiffDialogOpen(true)
  }

  // ---------- Tag dialog open/close --------------------------------------

  function openTagDialog(taskId: string) {
    setTagDialogTaskId(taskId)
  }

  function applyFilters(patch: Record<string, string>) {
    updateUrl({
      task_type: patch.task_type ?? filters.task_type,
      status: patch.status ?? filters.status,
      q: patch.search ?? filters.search,
      since: patch.since ?? filters.since,
    })
  }

  return (
    <div className="ac-page" data-testid="log-center">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Logs &amp; Traces</h1>
        <span className="ac-page__hint">
          手动刷新 · ⌘R / F5 · ⌘K 唤起命令面板
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button
            type="button"
            className="ac-btn"
            onClick={() => setPaletteOpen(true)}
            data-testid="open-palette"
          >
            ⌘K 命令面板
          </button>
          <button
            type="button"
            className="ac-btn ac-btn--primary"
            onClick={refreshAll}
            disabled={traceListQuery.isFetching}
            data-testid="refresh-btn"
          >
            {traceListQuery.isFetching ? <span className="spinner" /> : null}
            {traceListQuery.isFetching ? '正在刷新…' : 'Refresh'}
          </button>
        </div>
      </div>

      {traceListQuery.isError && (
        <div className="ac-error-banner" data-testid="list-error">
          任务列表载入失败:{(traceListQuery.error as Error)?.message ?? '未知错误'}
        </div>
      )}

      <LogCenterFilterBar
        filters={filters}
        onChange={(next) => {
          // LogCenterFilterBar callback contract = AdminFilters → URL
          updateUrl({
            task_type: next.task_type,
            status: next.status,
            q: next.search,
            since: next.since,
          })
        }}
        onRefresh={refreshAll}
        refreshing={traceListQuery.isFetching}
      />

      <div className="ac-master-detail">
        <section className="ac-master">
          <LogCenterTaskList
            traces={traces}
            loading={traceListQuery.isFetching && traces.length === 0}
            selectedTraceId={selectedTraceId}
            onSelect={(id) => updateUrl({ trace: id })}
            onReplay={(id) => setReplayDialogTraceId(id)}
            replayingFor={replayingFor}
            capabilities={capabilities}
            searchKeyword={filters.search}
            diffSelection={diffSelection}
            onToggleDiffSelection={toggleDiffSelection}
            onOpenDiff={openDiffDialog}
            tagsByTask={Object.fromEntries(
              Object.entries(tagCache).map(([k, v]) => [k, v.map((t) => t.tag)]),
            )}
            onOpenTags={openTagDialog}
          />
          <LogCenterErrorAggregation traces={traces} />
        </section>

        <LogCenterDetailPanel
          trace={traceQuery.data?.trace ?? null}
          nodes={traceQuery.data?.nodes ?? []}
          loadingNodes={traceQuery.isFetching && (traceQuery.data?.nodes ?? []).length === 0}
          onOpenNode={onOpenNode}
          tags={tagsQuery.data ?? []}
          onManageTags={() => selectedTraceId && openTagDialog(selectedTraceId)}
          diff={
            diffResult
              ? {
                  rightTraceId:
                    diffSelection[1] ?? diffSelection[0] ?? '',
                  rightTraceType: '',
                  entries: diffResult,
                }
              : null
          }
        />
      </div>

      <LogCenterCommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        recentTaskIds={traces.map((t) => t.id)}
        filters={filters}
        onApplyFilters={applyFilters}
      />

      <ReplayDialog
        open={Boolean(replayDialogTraceId)}
        traceId={replayDialogTraceId}
        capabilities={capabilities}
        onClose={() => setReplayDialogTraceId(null)}
        onConfirm={(id) => replayMutation.mutate(id)}
        onNotify={notify}
      />

      <TagSelector
        open={Boolean(tagDialogTaskId)}
        taskId={tagDialogTaskId}
        initialTags={
          tagDialogTaskId
            ? tagCache[tagDialogTaskId] ??
              (selectedTraceId === tagDialogTaskId ? tagsQuery.data ?? [] : [])
            : []
        }
        capabilities={capabilities}
        onClose={() => setTagDialogTaskId(null)}
        onSaved={(tags) => {
          if (!tagDialogTaskId) return
          setTagCache((cur) => ({ ...cur, [tagDialogTaskId]: tags }))
          if (selectedTraceId === tagDialogTaskId) {
            queryClient.invalidateQueries({ queryKey: ['admin', 'tags', selectedTraceId] })
          }
        }}
        onNotify={notify}
      />

      <DiffDialog
        open={diffDialogOpen}
        leftTraceId={diffSelection[0] ?? null}
        rightTraceId={diffSelection[1] ?? null}
        onClose={() => {
          setDiffDialogOpen(false)
          setDiffResult(null)
          setDiffError(null)
        }}
        onCompute={async (left, right) => {
          await diffMutation.mutateAsync({ left, right })
        }}
        loading={diffMutation.isPending}
        result={diffResult}
        error={diffError}
      />

      <NodeIODrawer
        open={Boolean(drawerNodeId)}
        traceId={selectedTraceId}
        nodeId={drawerNodeId}
        onClose={() => setDrawerNodeId(null)}
        onNotify={notify}
      />

      <PayloadWarningDialog
        open={payloadWarning.open}
        estimatedBytes={payloadWarning.bytes}
        onConfirm={() => {
          setPayloadWarning({ open: false, bytes: 0, nodeId: null })
          if (payloadWarning.nodeId) setDrawerNodeId(payloadWarning.nodeId)
        }}
        onCancel={() => setPayloadWarning({ open: false, bytes: 0, nodeId: null })}
      />

      {/* Toast host */}
      <div className="ac-toast-container" data-testid="toast-host">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={
              t.kind === 'error'
                ? 'ac-toast ac-toast--error'
                : t.kind === 'warn'
                  ? 'ac-toast ac-toast--warn'
                  : 'ac-toast'
            }
            data-testid="toast"
          >
            {t.msg}
          </div>
        ))}
      </div>

      {traceListQuery.isFetching && (
        <div
          style={{
            position: 'fixed',
            bottom: 18,
            left: 18,
            color: 'var(--ac-ink-muted)',
            fontSize: 11,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <Loader2 size={12} /> 正在刷新…
        </div>
      )}
    </div>
  )
}

export default LogCenter

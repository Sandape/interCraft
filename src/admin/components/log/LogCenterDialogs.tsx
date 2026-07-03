/**
 * LogCenter dialogs — REQ-039 B2.
 *
 * Three dialogs:
 *  - TagSelector (5 presets + custom + Enter save)
 *  - ReplayDialog (二次确认)
 *  - DiffDialog (pick 2 traces → show node-aligned fields)
 *
 * Capabilities gating:
 *  - missing TASK_TAG → TagSelector enters read-only mode (FR-020)
 *  - missing REPLAY_TRIGGER → ReplayDialog hides the trigger button
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { adminConsoleApi } from '@/api/admin-console'
import type {
  AdminDiffNodeEntry,
  AdminPresetTag,
  AdminTaskTag,
} from '@/types/admin-console'
import { ADMIN_PRESET_TAGS } from '@/types/admin-console'

// ---------------------------------------------------------------------------
// Shared modal scaffolding
// ---------------------------------------------------------------------------

function Modal({
  title,
  open,
  onClose,
  children,
  width,
}: {
  title: string
  open: boolean
  onClose: () => void
  children: ReactNode
  width?: number
}) {
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div
      className="ac-modal-overlay"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      data-testid="modal-overlay"
    >
      <div
        className="ac-modal"
        style={width ? { width } : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 className="ac-modal__title">{title}</h3>
          <button
            type="button"
            className="ac-btn ac-btn--ghost"
            onClick={onClose}
            data-testid="modal-close"
            style={{ padding: '2px 8px' }}
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// TagSelector (FR-016..FR-020, FR-031, US4)
// ---------------------------------------------------------------------------

export interface TagSelectorProps {
  open: boolean
  taskId: string | null
  initialTags: AdminTaskTag[]
  capabilities: string[]
  onClose: () => void
  onSaved: (tags: AdminTaskTag[]) => void
  onNotify: (msg: string, kind?: 'info' | 'warn' | 'error') => void
}

const TAG_REGEX = /^[A-Za-z0-9_\-一-龥 ]+$/

export function TagSelector({
  open,
  taskId,
  initialTags,
  capabilities,
  onClose,
  onSaved,
  onNotify,
}: TagSelectorProps): ReactNode {
  const [tags, setTags] = useState<AdminTaskTag[]>(initialTags)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const readOnly = !capabilities.includes('TASK_TAG')

  useEffect(() => {
    if (open) setTags(initialTags)
  }, [open, initialTags])

  const presets = useMemo(() => ADMIN_PRESET_TAGS, [])

  if (!taskId) return null

  async function addTag(text: string) {
    if (!text) return
    const trimmed = text.trim()
    if (trimmed.length === 0 || trimmed.length > 50) {
      onNotify('标签长度需在 1-50 字符之间', 'warn')
      return
    }
    if (!TAG_REGEX.test(trimmed)) {
      onNotify('标签只能包含字母 / 数字 / _ - / CJK / 空格', 'warn')
      return
    }
    if (tags.some((t) => t.tag === trimmed)) {
      onNotify(`标签 "${trimmed}" 已存在`, 'warn')
      return
    }
    setBusy(true)
    try {
      const row = await adminConsoleApi.addTag(taskId!, { tag: trimmed })
      const next = [...tags, row].sort((a, b) => a.tag.localeCompare(b.tag))
      setTags(next)
      onSaved(next)
      // FR-019: write-through to localStorage as offline cache only.
      try {
        const cache = readCache()
        cache[taskId!] = next
        writeCache(cache)
      } catch {
        /* ignore quota errors */
      }
      onNotify('标签已保存', 'info')
      setInput('')
    } catch (e) {
      const msg = e instanceof Error ? e.message : '保存失败'
      onNotify(msg, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function removeTag(text: string) {
    setBusy(true)
    try {
      await adminConsoleApi.deleteTag(taskId!, text)
      const next = tags.filter((t) => t.tag !== text)
      setTags(next)
      onSaved(next)
      try {
        const cache = readCache()
        cache[taskId!] = next
        writeCache(cache)
      } catch {
        /* ignore */
      }
      onNotify('标签已删除', 'info')
    } catch (e) {
      const msg = e instanceof Error ? e.message : '删除失败'
      onNotify(msg, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="任务标签" open={open} onClose={onClose} width={520}>
      {readOnly && (
        <div
          className="ac-error-banner"
          style={{ background: 'rgba(245, 158, 11, 0.12)', color: 'var(--ac-pending)' }}
        >
          当前账号无 TASK_TAG 权限,标签为只读。
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
        {presets.map((p) => {
          const owned = tags.some((t) => t.tag === p)
          return (
            <button
              key={p}
              type="button"
              disabled={readOnly || busy || owned}
              className={`ac-tag-chip ac-tag-chip--${presetClass(p)}`}
              style={{
                cursor: readOnly ? 'default' : 'pointer',
                padding: '4px 10px',
                fontSize: 11,
                opacity: owned ? 0.55 : 1,
                border: 0,
              }}
              onClick={() => addTag(p)}
              data-testid={`tag-preset-${p}`}
            >
              {p}
            </button>
          )
        })}
        {tags
          .filter((t) => !(presets as string[]).includes(t.tag))
          .map((t) => (
            <span
              key={t.tag}
              className="ac-tag-chip ac-tag-chip--monitoring"
              style={{ padding: '4px 10px', fontSize: 11 }}
            >
              {t.tag}
              {!readOnly && (
                <button
                  type="button"
                  className="ac-btn ac-btn--ghost"
                  style={{ padding: 0, marginLeft: 4, fontSize: 11, color: 'inherit' }}
                  onClick={() => removeTag(t.tag)}
                  data-testid={`tag-remove-${t.tag}`}
                >
                  ✕
                </button>
              )}
            </span>
          ))}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="自定义标签(Enter 保存)"
          maxLength={50}
          disabled={readOnly}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addTag(input)
            }
          }}
          data-testid="tag-input"
          style={{
            flex: 1,
            background: 'var(--ac-bg)',
            border: '1px solid var(--ac-border)',
            color: 'var(--ac-ink)',
            borderRadius: 4,
            padding: '6px 10px',
            fontSize: 12,
          }}
        />
        <button
          type="button"
          className="ac-btn ac-btn--primary"
          onClick={() => addTag(input)}
          disabled={readOnly || busy || !input.trim()}
          data-testid="tag-save"
        >
          保存
        </button>
      </div>
      <div style={{ marginTop: 12, fontSize: 11, color: 'var(--ac-ink-faint)' }}>
        标签规则:1-50 个字符,允许字母/数字/_/-/CJK/空格。删除为硬删除,重新添加视为新建。
      </div>
    </Modal>
  )
}

function presetClass(p: AdminPresetTag): string {
  return p
}

// ---------------------------------------------------------------------------
// ReplayDialog (FR-006, FR-009, FR-032)
// ---------------------------------------------------------------------------

export interface ReplayDialogProps {
  open: boolean
  traceId: string | null
  capabilities: string[]
  onClose: () => void
  onConfirm: (traceId: string) => void
  onNotify: (msg: string, kind?: 'info' | 'warn' | 'error') => void
}

export function ReplayDialog({
  open,
  traceId,
  capabilities,
  onClose,
  onConfirm,
  onNotify,
}: ReplayDialogProps): ReactNode {
  const hasCap = capabilities.includes('REPLAY_TRIGGER')
  useEffect(() => {
    if (open && !hasCap) onNotify('需要 REPLAY_TRIGGER 权限', 'warn')
  }, [open, hasCap, onNotify])

  if (!traceId) return null
  return (
    <Modal title="Replay 该任务" open={open} onClose={onClose} width={460}>
      <p style={{ fontSize: 12, color: 'var(--ac-ink-muted)', marginBottom: 16 }}>
        Replay 会基于该 trace 的 <code>input_payload</code> 快照在服务端创建一个新的 trace
        (标注 <code>replay_of</code>=原 trace),prompt_version + model 保持不变。成功后请手动 Refresh 或等待 10s
        后系统刷新即可看到新 trace。
      </p>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button type="button" className="ac-btn" onClick={onClose} data-testid="replay-cancel">
          取消
        </button>
        <button
          type="button"
          className="ac-btn ac-btn--primary"
          onClick={() => {
            if (!hasCap) {
              onNotify('需要 REPLAY_TRIGGER 权限', 'warn')
              return
            }
            onConfirm(traceId)
          }}
          disabled={!hasCap}
          title={hasCap ? '点击执行 Replay' : '需要 REPLAY_TRIGGER 权限'}
          data-testid="replay-confirm"
        >
          {hasCap ? '确认 Replay' : '🔒 权限不足'}
        </button>
      </div>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// DiffDialog (FR-011..FR-015, FR-033)
// ---------------------------------------------------------------------------

export interface DiffDialogProps {
  open: boolean
  leftTraceId: string | null
  rightTraceId: string | null
  onClose: () => void
  onCompute: (left: string, right: string) => Promise<void>
  loading: boolean
  result: AdminDiffNodeEntry[] | null
  error: string | null
}

export function DiffDialog({
  open,
  leftTraceId,
  rightTraceId,
  onClose,
  onCompute,
  loading,
  result,
  error,
}: DiffDialogProps): ReactNode {
  const [left, setLeft] = useState(leftTraceId ?? '')
  const [right, setRight] = useState(rightTraceId ?? '')

  useEffect(() => {
    if (open) {
      setLeft(leftTraceId ?? '')
      setRight(rightTraceId ?? '')
    }
  }, [open, leftTraceId, rightTraceId])

  return (
    <Modal title="Trace Diff" open={open} onClose={onClose} width={680}>
      <p style={{ fontSize: 12, color: 'var(--ac-ink-muted)', marginBottom: 12 }}>
        节点级 diff,基于 <code>node_name</code> 对齐,字段级 add / del / mod 三色标记。
        跨 task_type 会被后端 400 拒绝 (FR-012)。
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          value={left}
          onChange={(e) => setLeft(e.target.value)}
          placeholder="left_trace_id"
          className="ac-mono"
          data-testid="diff-left"
          style={{
            background: 'var(--ac-bg)',
            border: '1px solid var(--ac-border)',
            color: 'var(--ac-ink)',
            borderRadius: 4,
            padding: '6px 10px',
            fontSize: 11,
          }}
        />
        <input
          type="text"
          value={right}
          onChange={(e) => setRight(e.target.value)}
          placeholder="right_trace_id"
          className="ac-mono"
          data-testid="diff-right"
          style={{
            background: 'var(--ac-bg)',
            border: '1px solid var(--ac-border)',
            color: 'var(--ac-ink)',
            borderRadius: 4,
            padding: '6px 10px',
            fontSize: 11,
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 16 }}>
        <button
          type="button"
          className="ac-btn ac-btn--primary"
          onClick={() => onCompute(left, right)}
          disabled={loading || !left || !right}
          data-testid="diff-confirm"
        >
          {loading ? <span className="spinner" /> : null}
          {loading ? '计算中…' : '计算 Diff'}
        </button>
      </div>
      {error && (
        <div className="ac-error-banner" data-testid="diff-error">
          {error}
        </div>
      )}
      {result && result.length === 0 && (
        <div className="ac-empty" data-testid="diff-empty">
          两 trace 字段一致,无差异。
        </div>
      )}
      {result && result.length > 0 && (
        <div
          style={{
            maxHeight: 360,
            overflow: 'auto',
            border: '1px solid var(--ac-border-subtle)',
            borderRadius: 4,
          }}
          data-testid="diff-result"
        >
          {result.map((entry, idx) => (
            <DiffRow key={`${entry.node_name}-${idx}`} entry={entry} />
          ))}
        </div>
      )}
    </Modal>
  )
}

function DiffRow({ entry }: { entry: AdminDiffNodeEntry }): ReactNode {
  const accent =
    entry.side === 'left'
      ? 'var(--ac-failed)'
      : entry.side === 'right'
        ? 'var(--ac-success)'
        : 'var(--ac-pending)'
  return (
    <div
      style={{
        padding: 10,
        borderBottom: '1px solid var(--ac-border-subtle)',
        fontFamily: 'var(--ac-mono)',
        fontSize: 11,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ color: accent }}>{entry.side.toUpperCase()}</span>
        <span style={{ color: 'var(--ac-ink)' }}>{entry.node_name}</span>
        {entry.status_left && entry.status_right && (
          <span style={{ color: 'var(--ac-ink-faint)' }}>
            {entry.status_left} → {entry.status_right}
          </span>
        )}
      </div>
      {entry.fields.length === 0 ? (
        <div style={{ color: 'var(--ac-ink-faint)' }}>(节点元数据一致)</div>
      ) : (
        entry.fields.map((f, idx) => (
          <div
            key={idx}
            style={{
              display: 'grid',
              gridTemplateColumns: '60px 220px 1fr 1fr',
              gap: 8,
              padding: '2px 0',
              color:
                f.op === 'add'
                  ? 'var(--ac-success)'
                  : f.op === 'del'
                    ? 'var(--ac-failed)'
                    : 'var(--ac-pending)',
            }}
          >
            <span>{f.op}</span>
            <span>{f.path}</span>
            <span style={{ color: 'var(--ac-ink-muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {f.left !== undefined ? JSON.stringify(f.left) : '∅'}
            </span>
            <span style={{ color: 'var(--ac-ink-muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {f.right !== undefined ? JSON.stringify(f.right) : '∅'}
            </span>
          </div>
        ))
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// NodeIO drawer (FR-025..FR-029, US6)
// ---------------------------------------------------------------------------

export interface NodeIODrawerProps {
  open: boolean
  traceId: string | null
  nodeId: string | null
  onClose: () => void
  onNotify: (msg: string, kind?: 'info' | 'warn' | 'error') => void
}

const PAGE_BYTES = 51200 // 50 KB per chunk
const HARD_LIMIT_BYTES = 50 * 1024 * 1024 // 50 MB

export function NodeIODrawer({
  open,
  traceId,
  nodeId,
  onClose,
  onNotify,
}: NodeIODrawerProps): ReactNode {
  const [chunks, setChunks] = useState<string[]>([])
  const [totalSize, setTotalSize] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [hint, setHint] = useState<string>('')

  useEffect(() => {
    if (!open || !traceId || !nodeId) {
      setChunks([])
      setTotalSize(null)
      setConfirmed(false)
      setHint('')
      return
    }
    // We don't know the total in advance, but the proxy /api returns
    // X-Total-Size header. For <50KB we render straight; for >2MB we
    // require confirmation. We optimistically fetch the first chunk
    // and then re-evaluate.
    let canceled = false
    ;(async () => {
      setLoading(true)
      try {
        const data = await adminConsoleApi.fetchNodePayload(traceId, nodeId, { offset: 0, limit: PAGE_BYTES })
        if (canceled) return
        const size = (data ?? '').length
        if (size === 0) {
          setChunks([data])
          setTotalSize(data.length)
          setHint('无内容')
        } else {
          setChunks([data])
          setTotalSize(data.length)
          if (data.length >= PAGE_BYTES) {
            setHint(`已载入 1 页 (≈${Math.round(data.length / 1024)}KB),可点击 "Load more" 追加`)
          }
        }
      } catch (e: unknown) {
        if (canceled) return
        const err = e as { message?: string; status?: number; details?: { reason?: string } }
        if (err?.status === 413 || err?.details?.reason === 'payload_too_large') {
          onNotify(`payload >50MB,超过服务端硬上限 ${HARD_LIMIT_BYTES} 字节。请联系 devops 导出原始。`, 'error')
        } else {
          onNotify(err.message ?? '载入失败', 'error')
        }
      } finally {
        if (!canceled) setLoading(false)
      }
    })()
    return () => {
      canceled = true
    }
  }, [open, traceId, nodeId, onNotify])

  if (!open || !traceId || !nodeId) return null
  const [pureNodeId, io] = nodeId.split('::')

  function loadMore() {
    if (!traceId || !nodeId) return
    if (!totalSize && chunks.length === 0) return
    setLoading(true)
    adminConsoleApi
      .fetchNodePayload(traceId, nodeId, {
        offset: chunks.reduce((acc, c) => acc + c.length, 0),
        limit: PAGE_BYTES,
      })
      .then((data) => {
        setChunks((c) => [...c, data])
        // If we got less than a full page, this is the last one.
        if (data.length < PAGE_BYTES) {
          setHint('已载入全部')
        }
      })
      .catch((e: unknown) => {
        const err = e as { message?: string }
        onNotify(err.message ?? '载入下一页失败', 'error')
      })
      .finally(() => setLoading(false))
  }

  return (
    <>
      <div className="ac-drawer-overlay" onClick={onClose} data-testid="node-drawer-overlay" />
      <aside
        className="ac-drawer"
        role="dialog"
        aria-modal="true"
        data-testid="node-drawer"
      >
        <div className="ac-drawer__header">
          <h3 className="ac-drawer__title">
            {io?.toUpperCase()} · node:{pureNodeId.slice(0, 12)}…
          </h3>
          <button
            type="button"
            className="ac-btn ac-btn--ghost"
            onClick={onClose}
            data-testid="node-drawer-close"
          >
            ✕
          </button>
        </div>
        <div className="ac-drawer__body" data-testid="node-drawer-body">
          {chunks.length === 0 && loading ? (
            <div className="ac-loading">
              <span className="spinner" /> 载入中…
            </div>
          ) : chunks.length === 0 ? (
            <div className="ac-empty">该节点为空。</div>
          ) : (
            chunks.join('')
          )}
        </div>
        <div className="ac-drawer__footer">
          <span
            style={{
              fontSize: 11,
              color: 'var(--ac-ink-muted)',
              marginRight: 'auto',
              fontFamily: 'var(--ac-mono)',
            }}
            data-testid="node-drawer-hint"
          >
            {hint || (chunks.length ? `${chunks.length} 页 · ${chunks.reduce((a, c) => a + c.length, 0)} 字节` : '')}
          </span>
          {chunks.length > 0 && chunks[chunks.length - 1].length >= PAGE_BYTES && (
            <button
              type="button"
              className="ac-btn"
              onClick={loadMore}
              disabled={loading}
              data-testid="load-more"
            >
              {loading ? <span className="spinner" /> : null}
              Load more
            </button>
          )}
          <button type="button" className="ac-btn" onClick={onClose}>关闭</button>
        </div>
      </aside>
    </>
  )
}

// ---------------------------------------------------------------------------
// Payload >2MB warning dialog (FR-028, US6 AC3)
// ---------------------------------------------------------------------------

export interface PayloadWarningDialogProps {
  open: boolean
  estimatedBytes: number
  onConfirm: () => void
  onCancel: () => void
}

export function PayloadWarningDialog({
  open,
  estimatedBytes,
  onConfirm,
  onCancel,
}: PayloadWarningDialogProps): ReactNode {
  if (!open) return null
  return (
    <Modal title="Payload 过大" open={open} onClose={onCancel} width={460}>
      <p style={{ fontSize: 12, color: 'var(--ac-ink-muted)', marginBottom: 12 }}>
        payload &gt;2MB ({Math.round(estimatedBytes / 1024)} KB),建议先在 detail panel 节点 IO 字段裁剪后再查看,
        否则浏览器可能挂起。是否继续载入?
      </p>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button type="button" className="ac-btn" onClick={onCancel} data-testid="payload-cancel">
          取消
        </button>
        <button
          type="button"
          className="ac-btn ac-btn--primary"
          onClick={onConfirm}
          data-testid="payload-confirm"
        >
          仍然继续
        </button>
      </div>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// localStorage tag cache helpers (FR-019)
// ---------------------------------------------------------------------------

function readCache(): Record<string, AdminTaskTag[]> {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem('log-center:tags:v1')
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (typeof parsed !== 'object' || parsed === null) return {}
    return parsed as Record<string, AdminTaskTag[]>
  } catch {
    return {}
  }
}

function writeCache(data: Record<string, AdminTaskTag[]>): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem('log-center:tags:v1', JSON.stringify(data))
  } catch {
    /* quota — ignore */
  }
}

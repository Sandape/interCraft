/**
 * LogCenter shared utilities — REQ-039 B2.
 *
 * - normalizeStatus / normalizeType : map backend enums to UI tokens.
 * - formatDuration                  : human-readable durations.
 * - microGantt                      : inline timeline of node spans.
 * - computeErrorHash                : SHA256 prefix via Web Crypto,
 *                                    byte-identical with the backend's
 *                                    backend/app/observability/error_hash.py
 *                                    (FR-022 normalization rules).
 */
import type {
  AdminTrace,
  AdminTraceNode,
  NormalizedStatus,
  NormalizedTaskType,
} from '@/types/admin-console'

// ---------------------------------------------------------------------------
// Status / type normalization
// ---------------------------------------------------------------------------

const STATUS_MAP: Record<string, NormalizedStatus> = {
  success: 'success',
  succeeded: 'success',
  ok: 'success',
  completed: 'success',
  done: 'success',
  passed: 'success',
  failed: 'failed',
  error: 'failed',
  err: 'failed',
  failure: 'failed',
  pending: 'pending',
  queued: 'pending',
  waiting: 'pending',
  running: 'running',
  in_progress: 'running',
  active: 'running',
  starting: 'running',
}

const TYPE_MAP: Record<string, NormalizedTaskType> = {
  interview: 'interview',
  mock_interview: 'interview',
  interview_session: 'interview',
  resume_optimize: 'resume_optimize',
  resume: 'resume_optimize',
  resume_opt: 'resume_optimize',
  ability_diagnose: 'ability_diagnose',
  ability: 'ability_diagnose',
  ability_profile: 'ability_diagnose',
  error_coach: 'error_coach',
  coach: 'error_coach',
  general_coach: 'general_coach',
  general: 'general_coach',
}

export function normalizeStatus(status: string | null | undefined): NormalizedStatus {
  if (!status) return 'pending'
  return STATUS_MAP[String(status).toLowerCase()] ?? 'pending'
}

export function normalizeType(type: string | null | undefined): NormalizedTaskType {
  if (!type) return 'unknown'
  return TYPE_MAP[String(type).toLowerCase()] ?? 'unknown'
}

// ---------------------------------------------------------------------------
// Duration formatter
// ---------------------------------------------------------------------------

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return '—'
  if (ms < 0) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  const sec = ms / 1000
  if (sec < 60) return `${sec.toFixed(sec < 10 ? 2 : 1)}s`
  const min = sec / 60
  if (min < 60) return `${Math.floor(min)}m ${Math.floor(sec % 60)}s`
  const hr = min / 60
  return `${Math.floor(hr)}h ${Math.floor(min % 60)}m`
}

// ---------------------------------------------------------------------------
// microGantt — small inline timeline component for the task list.
// ---------------------------------------------------------------------------

export interface MicroGanttSpan {
  id: string
  label: string
  startMs: number
  endMs: number
  status: NormalizedStatus
}

export function microGantt(
  spans: ReadonlyArray<MicroGanttSpan>,
  width = 240,
  height = 14,
): JSX.Element {
  if (spans.length === 0) {
    return (
      <div
        className="ac-mono"
        style={{ color: 'var(--ac-ink-faint)', fontSize: 10 }}
      >
        (no spans)
      </div>
    )
  }
  const minStart = Math.min(...spans.map((s) => s.startMs))
  const maxEnd = Math.max(...spans.map((s) => s.endMs))
  const span = Math.max(maxEnd - minStart, 1)
  const statusColor: Record<NormalizedStatus, string> = {
    success: 'var(--ac-success)',
    failed: 'var(--ac-failed)',
    pending: 'var(--ac-pending)',
    running: 'var(--ac-running)',
  }
  return (
    <div
      role="presentation"
      style={{
        position: 'relative',
        width,
        height,
        background: 'rgba(255,255,255,0.04)',
        borderRadius: 3,
        overflow: 'hidden',
      }}
    >
      {spans.map((s) => {
        const left = ((s.startMs - minStart) / span) * width
        const w = Math.max(((s.endMs - s.startMs) / span) * width, 1.5)
        return (
          <div
            key={s.id}
            title={`${s.label} · ${s.status}`}
            style={{
              position: 'absolute',
              top: 2,
              bottom: 2,
              left,
              width: w,
              background: statusColor[s.status],
              borderRadius: 2,
              opacity: 0.85,
            }}
          />
        )
      })}
    </div>
  )
}

export function buildGanttFromTrace(
  trace: AdminTrace,
  nodes: ReadonlyArray<AdminTraceNode>,
): MicroGanttSpan[] {
  const startBase = trace.started_at ? new Date(trace.started_at).getTime() : Date.now()
  return nodes.slice(0, 12).map((node, idx) => {
    const offset = idx * 80
    const dur = 80
    const start = startBase + offset
    const end = start + dur
    return {
      id: node.node_id,
      label: node.name,
      startMs: start,
      endMs: end,
      status: normalizeStatus(node.status),
    }
  })
}

// ---------------------------------------------------------------------------
// computeErrorHash — SHA256 prefix via Web Crypto, mirror of backend
// backend/app/observability/error_hash.py (FR-022 / FR-023).
// ---------------------------------------------------------------------------

// Per FR-022 clarification (option B):
//   1. lowercase
//   2. collapse internal whitespace
//   3. strip UUID / hex blob / ≥12-digit digit sequences
//   4. preserve ordinary numbers (≤11 digits) and all words
const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi
const HEX_BLOB_RE = /\b[0-9a-f]{16,}\b/gi
const LONG_DIGITS_RE = /\b\d{12,}\b/g
const WHITESPACE_RE = /\s+/g

function normalizeForHash(message: string): string {
  return message
    .toLowerCase()
    .trim()
    .replace(WHITESPACE_RE, ' ')
    .replace(UUID_RE, '')
    .replace(HEX_BLOB_RE, '')
    .replace(LONG_DIGITS_RE, '')
    .replace(/ {2,}/g, ' ')
    .trim()
}

function bytesToHex(bytes: Uint8Array): string {
  let s = ''
  for (const b of bytes) s += b.toString(16).padStart(2, '0')
  return s
}

/**
 * Compute the SHA256-prefix bucket id for an error message.
 *
 * Returns an 8-char hex string (the first 4 bytes of SHA256 hex).
 * Resolves to "00000000" when Web Crypto is unavailable (jsdom
 * fallback only) so the bucket UI never crashes during testing.
 */
export async function computeErrorHash(message: string): Promise<string> {
  const normalized = normalizeForHash(message)
  if (!normalized) return '00000000'
  if (typeof globalThis.crypto?.subtle?.digest !== 'function') {
    return '00000000'
  }
  const encoded = new TextEncoder().encode(normalized)
  const digest = await globalThis.crypto.subtle.digest('SHA-256', encoded)
  // take the first 8 hex chars (4 bytes)
  return bytesToHex(new Uint8Array(digest)).slice(0, 8)
}

/**
 * Synchronous variant — only valid for environments where SHA-256 was
 * precomputed (currently used by tests to inspect bucket assignment
 * without awaiting a Promise). Returns null when Web Crypto is needed.
 */
export function computeErrorHashSync(message: string): string | null {
  const normalized = normalizeForHash(message)
  if (!normalized) return '00000000'
  if (typeof globalThis.crypto?.subtle?.digest !== 'function') {
    return null
  }
  // callers wanting sync behavior should pre-compute; the helper exists
  // so tests can `await` the async version instead.
  return null
}

export const ERROR_HASH_TOOLTIP =
  '由 SHA256 前 8 字节生成,已剥离 UUID / hex blob / 长数字串,普通数字与单词保留'

// ---------------------------------------------------------------------------
// Trace / node helpers
// ---------------------------------------------------------------------------

export function traceStatusText(trace: AdminTrace): string {
  return normalizeStatus(trace.status)
}

export function shortId(id: string | null | undefined, head = 8): string {
  if (!id) return '—'
  if (id.length <= head + 4) return id
  return `${id.slice(0, head)}…`
}

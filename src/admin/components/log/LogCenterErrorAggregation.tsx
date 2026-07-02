/**
 * LogCenter error aggregation — REQ-039 B2 US5.
 *
 * Groups failed traces by `computeErrorHash(message)` using SHA256
 * prefix (Web Crypto). Tooltip text matches FR-024 verbatim. Buckets
 * with >100 traces gain an inline "展开最近 20 条" affordance per AC4.
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { AdminTrace } from '@/types/admin-console'
import { computeErrorHash, ERROR_HASH_TOOLTIP, shortId } from './index'

interface Props {
  traces: AdminTrace[]
}

interface Bucket {
  hash: string
  count: number
  sampleMessage: string
  traceIds: string[]
}

const STORAGE_KEY = 'log-center:tags:v1'

export function LogCenterErrorAggregation({ traces }: Props): ReactNode {
  const [hashes, setHashes] = useState<Record<string, string>>({})
  const [expandedBuckets, setExpandedBuckets] = useState<Set<string>>(new Set())

  // Compute hashes lazily for failed traces only (FR-022 / US5).
  useEffect(() => {
    const failedTraces = traces.filter((t) => t.status === 'failed' && t.error_message)
    const next: Record<string, string> = {}
    let canceled = false
    ;(async () => {
      for (const t of failedTraces) {
        if (canceled) return
        const key = `${t.id}::${(t.error_message ?? '').slice(0, 64)}`
        if (hashes[key]) {
          next[key] = hashes[key]
          continue
        }
        next[key] = await computeErrorHash(t.error_message ?? '')
      }
      if (!canceled) setHashes((cur) => ({ ...cur, ...next }))
    })()
    return () => {
      canceled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [traces])

  const buckets = useMemo<Map<string, Bucket>>(() => {
    const failedTraces = traces.filter((t) => t.status === 'failed' && t.error_message)
    const map = new Map<string, Bucket>()
    for (const t of failedTraces) {
      const key = `${t.id}::${(t.error_message ?? '').slice(0, 64)}`
      const hash = hashes[key] ?? computeErrorHashSyncFallback(t.error_message ?? '')
      if (!hash) continue
      const existing = map.get(hash)
      if (existing) {
        existing.count += 1
        existing.traceIds.push(t.id)
      } else {
        map.set(hash, {
          hash,
          count: 1,
          sampleMessage: t.error_message ?? '',
          traceIds: [t.id],
        })
      }
    }
    // Sort largest-first for visual priority.
    return new Map([...map.entries()].sort((a, b) => b[1].count - a[1].count))
  }, [traces, hashes])

  if (buckets.size === 0) {
    return (
      <div className="ac-error-buckets">
        <div className="ac-error-buckets__title">错误聚合</div>
        <div className="ac-empty" data-testid="error-empty">
          无失败任务,无需聚合。
        </div>
      </div>
    )
  }

  return (
    <div className="ac-error-buckets" data-testid="error-buckets">
      <div className="ac-error-buckets__title">错误聚合 (按 SHA256 前 8 字节)</div>
      {[...buckets.values()].map((bucket) => {
        const expanded = expandedBuckets.has(bucket.hash)
        return (
          <div key={bucket.hash}>
            <div className="ac-error-bucket" title={ERROR_HASH_TOOLTIP}>
              <span className="ac-error-bucket__hash">{bucket.hash}</span>
              <span className="ac-error-bucket__msg" title={bucket.sampleMessage}>
                {bucket.sampleMessage}
              </span>
              <span className="ac-error-bucket__count">{bucket.count}</span>
              {bucket.count > 100 && (
                <button
                  type="button"
                  className="ac-btn ac-btn--ghost"
                  style={{ fontSize: 10 }}
                  onClick={() =>
                    setExpandedBuckets((cur) => {
                      const next = new Set(cur)
                      if (next.has(bucket.hash)) next.delete(bucket.hash)
                      else next.add(bucket.hash)
                      return next
                    })
                  }
                  data-testid="expand-bucket"
                >
                  {expanded ? '收起' : '展开最近 20 条'}
                </button>
              )}
            </div>
            {expanded && bucket.count > 100 && (
              <div
                style={{
                  paddingLeft: 24,
                  paddingBottom: 8,
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: 4,
                  fontFamily: 'var(--ac-mono)',
                  fontSize: 10,
                  color: 'var(--ac-ink-muted)',
                }}
                data-testid="bucket-detail"
              >
                {bucket.traceIds.slice(-20).map((id) => (
                  <span key={id}>{shortId(id, 8)}</span>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// Fallback when Web Crypto isn't ready yet (initial SSR-style render):
// put every unhashable message into a single placeholder bucket so the
// UI shows a row instead of being empty until the async pass lands.
function computeErrorHashSyncFallback(message: string): string {
  return '00000000'
}

// Expose storage key so the page can pre-flight the tag offline cache
// (FR-019). The cache is a non-source-of-truth fallback only.
export { STORAGE_KEY as LOG_CENTER_TAGS_CACHE_KEY }

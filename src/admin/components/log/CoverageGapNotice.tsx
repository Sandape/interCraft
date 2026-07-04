/**
 * CoverageGapNotice — REQ-044 US5 / FR-025 / AC-25.1 + AC-25.2 + EC-3.
 *
 * Explicit notice when a product event has no correlated logs/traces.
 * Edge Cases line 328-329 "Product events exist without trace coverage
 * because a legacy path bypassed centralized instrumentation" →
 * three reasons enumerated, so maintainer can debug the gap rather
 * than silently receiving an empty list.
 *
 * Carries data-testid="coverage-gap-notice" so the empty-state is
 * distinguishable from a generic "no data" banner.
 */
import { AlertTriangle } from 'lucide-react'

interface CoverageGapNoticeProps {
  sourceType: 'incident' | 'signal' | 'badcase' | 'user' | 'trace' | 'unknown'
  sourceId: string | null
}

const REASONS = [
  {
    title: 'trace coverage gap',
    detail: '该 product event 上游链路尚未接入 OTel,trace span 未生成。',
  },
  {
    title: 'instrumentation incomplete',
    detail: '链路中部分节点未注册 langfuse / otel exporter,导致 span 缺失。',
  },
  {
    title: 'legacy path bypassed OTel',
    detail: '旧版本代码绕过集中埋点,直接命中下游服务,无法关联 trace。',
  },
]

export function CoverageGapNotice({ sourceType, sourceId }: CoverageGapNoticeProps) {
  return (
    <div
      className="ac-coverage-gap-notice"
      data-testid="coverage-gap-notice"
      data-source-type={sourceType}
      role="status"
      aria-live="polite"
    >
      <div className="ac-coverage-gap-notice__head">
        <AlertTriangle size={16} />
        <h3 data-testid="coverage-gap-title">No correlated logs found</h3>
      </div>
      <p className="ac-coverage-gap-notice__lead" data-testid="coverage-gap-lead">
        当前 source{' '}
        <code>
          {sourceType}
          {sourceId ? ':' + sourceId : ''}
        </code>{' '}
        没有可关联的 log / trace。可能原因:
      </p>
      <ul className="ac-coverage-gap-notice__reasons">
        {REASONS.map((r) => (
          <li
            key={r.title}
            className="ac-coverage-gap-notice__reason"
            data-testid={`coverage-gap-reason-${r.title.replace(/\s+/g, '-')}`}
          >
            <span className="ac-coverage-gap-notice__reason-title">{r.title}</span>
            <span className="ac-coverage-gap-notice__reason-detail">{r.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default CoverageGapNotice
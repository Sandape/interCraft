/**
 * DrilldownBanner — REQ-044 US5 / FR-024 / AC-24.2 + AC-24.4.
 *
 * Shown at the top of LogsAndTraces when the URL carries
 * `?from=<source_type>:<id>`. The banner surfaces the source label,
 * provides a "back to source" link that deep-links into the originating
 * workspace (incidents-badcases / command-center / users-accounts).
 *
 * When `trace=<id>` is also present in the URL, the banner auto-selects
 * that trace via the `onAutoSelectTrace` callback (AC-24.3).
 */
import { useEffect } from 'react'
import { ArrowLeft, Crosshair } from 'lucide-react'
import type { DrilldownSource } from '@/types/admin-logs'

interface DrilldownBannerProps {
  source: DrilldownSource
  onAutoSelectTrace?: (traceId: string) => void
  autoSelectTraceId?: string | null
}

const SOURCE_LABEL: Record<DrilldownSource['type'], string> = {
  incident: 'Incident',
  signal: 'Decision signal',
  badcase: 'Badcase',
  user: 'User / account',
  trace: 'Trace',
}

export function DrilldownBanner({
  source,
  onAutoSelectTrace,
  autoSelectTraceId,
}: DrilldownBannerProps) {
  // AC-24.3 — when the source type is "trace" and a trace id is
  // present, auto-select the trace so the right panel populates.
  useEffect(() => {
    if (source.type === 'trace' && autoSelectTraceId && onAutoSelectTrace) {
      onAutoSelectTrace(autoSelectTraceId)
    }
  }, [source.type, autoSelectTraceId, onAutoSelectTrace])

  return (
    <div
      className="ac-drilldown-banner"
      data-testid="drilldown-banner"
      data-source-type={source.type}
      data-source-id={source.id}
    >
      <div className="ac-drilldown-banner__icon" aria-hidden="true">
        <Crosshair size={14} />
      </div>
      <div className="ac-drilldown-banner__body">
        <span className="ac-drilldown-banner__label">Drilldown from</span>
        <span
          className="ac-drilldown-banner__source"
          data-testid="drilldown-source"
        >
          {SOURCE_LABEL[source.type]}: {source.id}
        </span>
        <a
          href={source.href}
          className="ac-drilldown-banner__back"
          data-testid="back-to-source"
        >
          <ArrowLeft size={12} /> back to source
        </a>
      </div>
    </div>
  )
}

export default DrilldownBanner
/**
 * DataStatusIndicator — REQ-044 FR-028 / SC-011.
 *
 * Inline indicator (icon + label) used by metric rows to surface
 * data quality. Composes :func:`QualityFlagsBadge` but with a left-side
 * position context (typically rendered as a row-level leading chip).
 */
import type { DataStatus } from '@/types/admin-governance'
import { QualityFlagsBadge } from './QualityFlagsBadge'

interface Props {
  status: DataStatus
  fetchedAt?: string
  contextLabel?: string
  'data-testid'?: string
}

export function DataStatusIndicator({
  status,
  fetchedAt,
  contextLabel,
  'data-testid': testId,
}: Props) {
  return (
    <div
      className="ac-data-status"
      data-testid={testId ?? `data-status-${status}`}
      data-status={status}
    >
      <QualityFlagsBadge status={status} size="sm" />
      {contextLabel ? (
        <span className="ac-data-status__context">{contextLabel}</span>
      ) : null}
      {fetchedAt ? (
        <span className="ac-data-status__fetched">{fetchedAt}</span>
      ) : null}
    </div>
  )
}

export default DataStatusIndicator

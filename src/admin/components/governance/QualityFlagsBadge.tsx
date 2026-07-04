/**
 * QualityFlagsBadge — REQ-044 FR-028 / SC-011.
 *
 * 5 data-quality states (FR-028 + SC-011):
 * - valid_zero (green): query returned no rows by design
 * - missing (grey): telemetry incomplete
 * - partial (yellow): some data, not all
 * - stale (orange): last updated beyond freshness threshold
 * - failed (red): calculation error
 *
 * Mirrors backend ``DataStatus`` Literal in
 * backend/app/modules/admin_console/governance/schemas.py.
 */
import type { DataStatus } from '@/types/admin-governance'

interface Props {
  status: DataStatus
  size?: 'sm' | 'md'
  'data-testid'?: string
}

const LABELS: Record<DataStatus, string> = {
  valid_zero: 'valid zero',
  missing: 'missing',
  partial: 'partial',
  stale: 'stale',
  failed: 'failed',
}

export function QualityFlagsBadge({
  status,
  size = 'md',
  'data-testid': testId,
}: Props) {
  return (
    <span
      className={`ac-quality-flag ac-quality-flag--${status}`}
      data-testid={`quality-flag-${status}`}
      data-quality-status={status}
      data-size={size}
      role="status"
    >
      <span className="ac-quality-flag__dot" aria-hidden="true" />
      {LABELS[status]}
    </span>
  )
}

export default QualityFlagsBadge

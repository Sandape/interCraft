/**
 * SnapshotCard — REQ-044 US7 FR-029.
 *
 * Renders one snapshot card in the Reports workspace list. Shows
 * snapshot_id / workspace / generated_at / metric count / late-arriving
 * warnings / cohort_definition_changed badge. Click to open the
 * SnapshotViewer (FR-030 AC-30.2).
 */
import type { ReviewSnapshotResponse } from '@/types/admin-review-snapshots'

interface Props {
  snapshot: ReviewSnapshotResponse
  onClick?: (snapshotId: string) => void
  'data-testid'?: string
}

export function SnapshotCard({
  snapshot,
  onClick,
  'data-testid': testId,
}: Props) {
  return (
    <button
      type="button"
      className="ac-snapshot-card"
      data-testid={testId ?? `snapshot-card-${snapshot.snapshot_id}`}
      data-snapshot-id={snapshot.snapshot_id}
      data-workspace={snapshot.workspace}
      onClick={() => onClick?.(snapshot.snapshot_id)}
    >
      <div className="ac-snapshot-card__header">
        <span className="ac-snapshot-card__title">
          {snapshot.workspace} · {snapshot.comparison_period}
        </span>
        <span className="ac-snapshot-card__id">{snapshot.snapshot_id}</span>
      </div>
      <div className="ac-snapshot-card__meta">
        <span className="ac-snapshot-card__meta-item">
          <strong>Generated:</strong> {snapshot.generated_at}
        </span>
        <span className="ac-snapshot-card__meta-item">
          <strong>By:</strong> {snapshot.generated_by}
        </span>
      </div>
      <div className="ac-snapshot-card__metrics">
        <span className="ac-snapshot-card__metric-count">
          {snapshot.frozen_values.length} frozen ·{' '}
          {snapshot.metric_definitions.length} defs ·{' '}
          {snapshot.evidence_links.length} evidence
        </span>
      </div>
      {snapshot.late_arriving_warnings.length > 0 ? (
        <div
          className="ac-snapshot-card__warn"
          data-testid="late-arriving-warning"
          role="status"
        >
          Late-arriving data: {snapshot.late_arriving_warnings.length} warnings
        </div>
      ) : null}
      {snapshot.cohort_definition_changed ? (
        <div
          className="ac-snapshot-card__warn ac-snapshot-card__warn--cohort"
          data-testid="cohort-change-warning"
          role="status"
        >
          Cohort definition changed since snapshot
        </div>
      ) : null}
      {snapshot.freshness_warnings.length > 0 ? (
        <div
          className="ac-snapshot-card__warn ac-snapshot-card__warn--freshness"
          data-testid="freshness-warning"
          role="status"
        >
          Freshness warnings: {snapshot.freshness_warnings.length}
        </div>
      ) : null}
    </button>
  )
}

export default SnapshotCard
/**
 * SnapshotViewer — REQ-044 US7 FR-029 + FR-030.
 *
 * Renders one snapshot's full detail:
 *
 *   - FrozenValueTable (Frozen at <timestamp>) — AC-30.2
 *   - CurrentValueTable (Current as of <now>) — AC-30.2
 *   - DeltaIndicator list (delta + late-arriving warning) — AC-30.3 + EC-1
 *   - AnnotationsEditor (immutable) — SC-012
 *   - Evidence link list (privacy-safe) — SC-012
 *   - Cohort change warning (EC-2)
 *   - Snapshot failed retry banner (EC-4)
 *
 * Per AC-30.4 the viewer exposes NO edit/delete affordance; the
 * backend rejects PUT/PATCH/DELETE with 405 SNAPSHOT_IMMUTABLE.
 */
import { QualityFlagsBadge } from '@/admin/components/governance/QualityFlagsBadge'
import { FrozenValueTable } from './FrozenValueTable'
import { CurrentValueTable } from './CurrentValueTable'
import { DeltaIndicator } from './DeltaIndicator'
import { AnnotationsEditor } from './AnnotationsEditor'
import type { ReviewSnapshotResponse } from '@/types/admin-review-snapshots'

interface Props {
  snapshot: ReviewSnapshotResponse | null
  loading?: boolean
  error?: Error | null
  onRetry?: () => void
  'data-testid'?: string
}

export function SnapshotViewer({
  snapshot,
  loading = false,
  error = null,
  onRetry,
  'data-testid': testId,
}: Props) {
  if (error) {
    return (
      <div
        className="ac-snapshot-viewer ac-snapshot-viewer--error"
        data-testid={testId ?? 'snapshot-viewer-error'}
        role="alert"
      >
        <div className="ac-snapshot-viewer__error-title" data-testid="snapshot-failed">
          Snapshot failed
        </div>
        <div
          className="ac-snapshot-viewer__error-body"
          data-testid="snapshot-failed-retry"
        >
          {error.message} — retry
          {onRetry ? (
            <button
              type="button"
              className="ac-snapshot-viewer__retry"
              data-testid="snapshot-retry-btn"
              onClick={() => onRetry()}
            >
              Retry
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  if (loading || !snapshot) {
    return (
      <div
        className="ac-snapshot-viewer ac-snapshot-viewer--loading"
        data-testid={testId ?? 'snapshot-viewer-loading'}
        role="status"
      >
        Loading snapshot…
      </div>
    )
  }

  return (
    <div
      className="ac-snapshot-viewer"
      data-testid={testId ?? 'snapshot-viewer'}
      data-snapshot-id={snapshot.snapshot_id}
      data-workspace={snapshot.workspace}
    >
      <div className="ac-snapshot-viewer__header">
        <h3 className="ac-snapshot-viewer__title">
          {snapshot.snapshot_id} · {snapshot.workspace}
        </h3>
        <span className="ac-snapshot-viewer__meta">
          Generated {snapshot.generated_at} by {snapshot.generated_by}
        </span>
        <span className="ac-snapshot-viewer__meta">
          Download URL:{' '}
          <a
            className="ac-snapshot-viewer__download"
            data-testid="snapshot-download-url"
            href={snapshot.download_url}
          >
            {snapshot.download_url}
          </a>
        </span>
      </div>

      {snapshot.cohort_definition_changed ? (
        <div
          className="ac-snapshot-viewer__warn ac-snapshot-viewer__warn--cohort"
          data-testid="cohort-change-warning-banner"
          role="status"
        >
          {snapshot.cohort_change_warning}
        </div>
      ) : null}

      {snapshot.late_arriving_warnings.length > 0 ? (
        <div
          className="ac-snapshot-viewer__warn ac-snapshot-viewer__warn--late"
          data-testid="late-arriving-banner"
          role="status"
        >
          Late-arriving data detected: {snapshot.late_arriving_warnings.length} warning(s)
        </div>
      ) : null}

      {snapshot.freshness_warnings.length > 0 ? (
        <div
          className="ac-snapshot-viewer__warn ac-snapshot-viewer__warn--freshness"
          data-testid="freshness-warning-banner"
          role="status"
        >
          Freshness warnings:
          <ul>
            {snapshot.freshness_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="ac-snapshot-viewer__compare">
        <FrozenValueTable
          values={snapshot.frozen_values}
          frozenAt={snapshot.frozen_values[0]?.captured_at ?? snapshot.generated_at}
        />
        <CurrentValueTable
          values={snapshot.current_values}
          fetchedAt={snapshot.current_values[0]?.captured_at ?? snapshot.generated_at}
        />
      </div>

      <div
        className="ac-snapshot-viewer__deltas"
        data-testid="comparison-deltas"
      >
        <h4 className="ac-snapshot-viewer__section-title">Comparison Deltas</h4>
        {snapshot.comparison_deltas.map((d) => (
          <DeltaIndicator key={d.metric_id} delta={d} />
        ))}
      </div>

      <div className="ac-snapshot-viewer__quality-flags">
        <h4 className="ac-snapshot-viewer__section-title">Quality Flags</h4>
        {Object.entries(snapshot.quality_flags).map(([metricId, status]) => (
          <div
            key={metricId}
            className="ac-snapshot-viewer__quality-row"
            data-metric-id={metricId}
          >
            <span className="ac-snapshot-viewer__quality-metric">{metricId}</span>
            <QualityFlagsBadge status={status} size="sm" />
          </div>
        ))}
      </div>

      <AnnotationsEditor snapshot={snapshot} />

      <div className="ac-snapshot-viewer__evidence">
        <h4 className="ac-snapshot-viewer__section-title">Evidence Links (privacy-safe)</h4>
        <ul
          className="ac-snapshot-viewer__evidence-list"
          data-testid="evidence-links-list"
        >
          {snapshot.evidence_links.map((e) => (
            <li
              key={`${e.kind}:${e.target_id}`}
              className="ac-snapshot-viewer__evidence-item"
              data-evidence-kind={e.kind}
              data-target-id={e.target_id}
            >
              <span className="ac-snapshot-viewer__evidence-kind">{e.kind}</span>
              <span className="ac-snapshot-viewer__evidence-label">{e.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default SnapshotViewer
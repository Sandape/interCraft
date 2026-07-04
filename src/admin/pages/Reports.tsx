/**
 * Reports — REQ-044 FR-005 / US7.
 *
 * PM Review Snapshots + Metric Trust workspace (FR-027~FR-030).
 * Surfaces:
 *
 *   - SnapshotGenerateForm (AC-29.5)
 *   - SnapshotCard list (AC-29.1)
 *   - SnapshotViewer detail (AC-30.1/30.2/30.3 + EC-1/EC-2/EC-4)
 *
 * The page is read-only after the snapshot is generated; PUT/PATCH/
 * DELETE return 405 SNAPSHOT_IMMUTABLE (AC-30.4). PM can re-generate
 * a new snapshot to supersede.
 */
import { useState } from 'react'
import {
  useCreateReviewSnapshot,
  useReviewSnapshots,
  useReviewSnapshot,
} from '@/admin/hooks/queries/useReviewSnapshots'
import { SnapshotCard } from '@/admin/components/reports/SnapshotCard'
import { SnapshotGenerateForm } from '@/admin/components/reports/SnapshotGenerateForm'
import { SnapshotViewer } from '@/admin/components/reports/SnapshotViewer'

export function Reports() {
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null)
  const list = useReviewSnapshots()
  const detail = useReviewSnapshot(selectedSnapshotId ?? '')
  const createMutation = useCreateReviewSnapshot()

  return (
    <div className="ac-page" data-testid="reports">
      <div className="ac-page__header">
        <h1 className="ac-page__title">Reports</h1>
        <span className="ac-page__hint">
          内部 review snapshot · frozen vs live · metric trust
        </span>
      </div>

      <div className="ac-reports-grid">
        <section
          className="ac-reports-grid__list"
          data-testid="reports-snapshot-list"
        >
          <h2 className="ac-reports-grid__list-title">Snapshots</h2>
          {list.isLoading ? (
            <div
              className="ac-reports-grid__empty"
              data-testid="snapshot-list-loading"
              role="status"
            >
              Loading snapshots…
            </div>
          ) : list.data && list.data.snapshots.length > 0 ? (
            <div
              className="ac-reports-grid__cards"
              data-testid="snapshot-list"
            >
              {list.data.snapshots.map((s) => (
                <SnapshotCard
                  key={s.snapshot_id}
                  snapshot={s}
                  onClick={(id) => setSelectedSnapshotId(id)}
                />
              ))}
            </div>
          ) : (
            <div
              className="ac-reports-grid__empty"
              data-testid="snapshot-list-empty"
              role="status"
            >
              No snapshots yet — generate one below.
            </div>
          )}
        </section>

        <section
          className="ac-reports-grid__viewer"
          data-testid="reports-snapshot-viewer"
        >
          <h2 className="ac-reports-grid__viewer-title">Snapshot detail</h2>
          <SnapshotViewer
            snapshot={detail.data ?? null}
            loading={detail.isLoading}
            error={detail.error as Error | null}
            onRetry={() => detail.refetch()}
          />
        </section>

        <section
          className="ac-reports-grid__generator"
          data-testid="reports-snapshot-generator"
        >
          <h2 className="ac-reports-grid__generator-title">Generate snapshot</h2>
          <SnapshotGenerateForm
            onCreated={(id) => {
              setSelectedSnapshotId(id)
            }}
          />
          {createMutation.isSuccess ? (
            <div
              className="ac-reports-grid__success"
              data-testid="snapshot-create-success"
              role="status"
            >
              Snapshot created: {createMutation.data?.snapshot_id}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  )
}

export default Reports
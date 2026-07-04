/**
 * AnnotationsEditor — REQ-044 US7 FR-029 SC-012.
 *
 * Read-only display of the snapshot's annotations (PM commentary
 * baked into the snapshot). Annotations are part of the SC-012
 * contract; AC-30.4 says snapshots are immutable, so the editor
 * is display-only (no edit affordance; mutations 405 server-side).
 */
import type { ReviewSnapshotResponse } from '@/types/admin-review-snapshots'

interface Props {
  snapshot: ReviewSnapshotResponse
  'data-testid'?: string
}

export function AnnotationsEditor({
  snapshot,
  'data-testid': testId,
}: Props) {
  return (
    <div
      className="ac-annotations-editor"
      data-testid={testId ?? 'annotations-editor'}
      data-snapshot-id={snapshot.snapshot_id}
    >
      <div className="ac-annotations-editor__header">
        <span className="ac-annotations-editor__title">Annotations</span>
        <span className="ac-annotations-editor__hint">
          (immutable, baked into snapshot)
        </span>
      </div>
      <div
        className="ac-annotations-editor__body"
        data-testid="annotations-body"
        role="article"
      >
        {snapshot.annotations || (
          <em className="ac-annotations-editor__empty">
            No annotations were added to this snapshot.
          </em>
        )}
      </div>
    </div>
  )
}

export default AnnotationsEditor
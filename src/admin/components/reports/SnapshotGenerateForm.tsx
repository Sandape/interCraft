/**
 * SnapshotGenerateForm — REQ-044 US7 FR-029 AC-29.5.
 *
 * Form to generate a new review snapshot. Required fields per AC-29.5:
 *
 *   - workspace selector (8 options from US6 WorkspaceId)
 *   - filter picker (period + optional cohort_changed + expired_record_ids)
 *   - annotations textarea (PM commentary, baked into the snapshot)
 *   - format selector (json / markdown)
 *
 * On submit -> useCreateReviewSnapshot mutation. On EC-3 expired
 * payloads -> 422 error rendered via snapshot-failed-banner.
 */
import { useState } from 'react'
import {
  useCreateReviewSnapshot,
} from '@/admin/hooks/queries/useReviewSnapshots'
import type {
  ReviewSnapshotFormat,
} from '@/types/admin-review-snapshots'
import type { WorkspaceId } from '@/types/admin-governance'

const WORKSPACES: WorkspaceId[] = [
  'command-center',
  'product-analytics',
  'ai-operations',
  'incidents-badcases',
  'logs-and-traces',
  'users-accounts',
  'reports',
  'governance',
]

const COMPARISON_PERIODS = [
  'vs prior week',
  'vs prior month',
  'vs prior quarter',
]

const FORMATS: ReviewSnapshotFormat[] = ['json', 'markdown']

interface Props {
  onCreated?: (snapshotId: string) => void
  'data-testid'?: string
}

export function SnapshotGenerateForm({
  onCreated,
  'data-testid': testId,
}: Props) {
  const [workspace, setWorkspace] = useState<WorkspaceId>('command-center')
  const [comparisonPeriod, setComparisonPeriod] = useState<string>(
    COMPARISON_PERIODS[0],
  )
  const [annotations, setAnnotations] = useState<string>('')
  const [format, setFormat] = useState<ReviewSnapshotFormat>('json')
  const [expiredRecordIds, setExpiredRecordIds] = useState<string>('')
  const [cohortChanged, setCohortChanged] = useState<boolean>(false)

  const createMutation = useCreateReviewSnapshot()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const filters: Record<string, unknown> = { period: 'rolling_7d' }
    if (expiredRecordIds.trim()) {
      filters.expired_record_ids = expiredRecordIds
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
    }
    if (cohortChanged) {
      filters.cohort_changed = true
    }
    createMutation.mutate(
      {
        workspace,
        filters,
        comparison_period: comparisonPeriod,
        annotations,
        format,
      },
      {
        onSuccess: (snap) => {
          onCreated?.(snap.snapshot_id)
        },
      },
    )
  }

  return (
    <form
      className="ac-snapshot-form"
      data-testid={testId ?? 'snapshot-generate-form'}
      onSubmit={handleSubmit}
    >
      <div className="ac-snapshot-form__row">
        <label htmlFor="snap-workspace" className="ac-snapshot-form__label">
          Workspace
        </label>
        <select
          id="snap-workspace"
          className="ac-snapshot-form__input ac-snapshot-form__workspace-selector"
          data-testid="workspace-selector"
          value={workspace}
          onChange={(e) => setWorkspace(e.target.value as WorkspaceId)}
        >
          {WORKSPACES.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </div>

      <div className="ac-snapshot-form__row">
        <label htmlFor="snap-comparison" className="ac-snapshot-form__label">
          Comparison Period
        </label>
        <select
          id="snap-comparison"
          className="ac-snapshot-form__input"
          data-testid="comparison-period-selector"
          value={comparisonPeriod}
          onChange={(e) => setComparisonPeriod(e.target.value)}
        >
          {COMPARISON_PERIODS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>

      <div className="ac-snapshot-form__row">
        <label htmlFor="snap-format" className="ac-snapshot-form__label">
          Format
        </label>
        <select
          id="snap-format"
          className="ac-snapshot-form__input ac-snapshot-form__format-selector"
          data-testid="format-selector"
          value={format}
          onChange={(e) =>
            setFormat(e.target.value as ReviewSnapshotFormat)
          }
        >
          {FORMATS.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </div>

      <div className="ac-snapshot-form__row">
        <label htmlFor="snap-annotations" className="ac-snapshot-form__label">
          Annotations (PM commentary, baked into snapshot)
        </label>
        <textarea
          id="snap-annotations"
          className="ac-snapshot-form__input ac-snapshot-form__annotations"
          data-testid="annotations-textarea"
          value={annotations}
          onChange={(e) => setAnnotations(e.target.value)}
          maxLength={4000}
          rows={4}
          placeholder="What is this snapshot for? Notes for the next reviewer…"
        />
      </div>

      <div className="ac-snapshot-form__row">
        <label htmlFor="snap-filter-picker" className="ac-snapshot-form__label">
          Filter Picker (period + cohort_changed + expired_record_ids)
        </label>
        <div data-testid="filter-picker" className="ac-snapshot-form__filter-picker">
          <label className="ac-snapshot-form__checkbox">
            <input
              type="checkbox"
              data-testid="cohort-changed-checkbox"
              checked={cohortChanged}
              onChange={(e) => setCohortChanged(e.target.checked)}
            />
            <span>cohort_changed</span>
          </label>
          <input
            id="snap-filter-picker"
            type="text"
            className="ac-snapshot-form__input"
            data-testid="expired-record-ids-input"
            value={expiredRecordIds}
            onChange={(e) => setExpiredRecordIds(e.target.value)}
            placeholder="expired_record_ids (comma separated, EC-3 trigger)"
          />
        </div>
      </div>

      {createMutation.isError ? (
        <div
          className="ac-snapshot-form__error"
          data-testid="snapshot-failed-banner"
          role="alert"
        >
          Snapshot failed:{' '}
          {(createMutation.error as Error)?.message ?? 'unknown error'} (retry)
        </div>
      ) : null}

      <div className="ac-snapshot-form__actions">
        <button
          type="submit"
          className="ac-snapshot-form__submit"
          data-testid="generate-snapshot-btn"
          disabled={createMutation.isPending}
        >
          {createMutation.isPending ? 'Generating…' : 'Generate snapshot'}
        </button>
      </div>
    </form>
  )
}

export default SnapshotGenerateForm
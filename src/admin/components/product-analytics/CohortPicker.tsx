/**
 * CohortPicker — REQ-044 US2 / FR-013.
 *
 * Renders a dropdown of cohorts. Selecting a cohort updates the
 * shared ``selectedCohortId`` so all panels (funnel / adoption /
 * retention) re-query with the same scope (AC-13.2).
 *
 * Edge Cases handled:
 *
 *   - EC-2: stale cohort surfaces an explicit "stale cohort" badge so
 *     users know the definition may have drifted since the snapshot.
 *   - AC-13.3: every cohort row shows population count +
 *     last_computed_at timestamp.
 */
import type { CohortSegment } from '@/types/admin-product-analytics'

interface CohortPickerProps {
  cohorts: CohortSegment[]
  selectedCohortId: string | null
  onSelect: (cohortId: string | null) => void
}

export function CohortPicker({
  cohorts,
  selectedCohortId,
  onSelect,
}: CohortPickerProps) {
  return (
    <div className="ac-pa-cohort-picker" data-testid="cohort-picker">
      <label
        htmlFor="ac-pa-cohort-select"
        className="ac-pa-cohort-picker__label"
      >
        Cohort
      </label>
      <select
        id="ac-pa-cohort-select"
        data-testid="cohort-select"
        className="ac-pa-cohort-picker__select"
        value={selectedCohortId ?? ''}
        onChange={(e) => onSelect(e.target.value || null)}
      >
        <option value="">— 全量 (no cohort) —</option>
        {cohorts.map((c) => (
          <option
            key={c.id}
            value={c.id}
            data-testid={`cohort-option-${c.id}`}
          >
            {c.name} ({c.population.toLocaleString()})
          </option>
        ))}
      </select>

      {selectedCohortId && (
        <CohortDetail
          cohort={
            cohorts.find((c) => c.id === selectedCohortId) ?? null
          }
        />
      )}
    </div>
  )
}

function CohortDetail({ cohort }: { cohort: CohortSegment | null }) {
  if (!cohort) {
    return (
      <div
        className="ac-pa-cohort-picker__detail"
        data-testid="cohort-detail-missing"
      >
        Unknown cohort
      </div>
    )
  }

  return (
    <div
      className="ac-pa-cohort-picker__detail"
      data-testid="cohort-detail"
    >
      <div
        className="ac-pa-cohort-picker__population"
        data-testid="cohort-population"
      >
        Population {cohort.population.toLocaleString()}
      </div>
      <div
        className="ac-pa-cohort-picker__last-computed"
        data-testid="cohort-last-computed-at"
      >
        Last computed {cohort.lastComputedAt}
      </div>
      {cohort.stale && (
        <div
          className="ac-pa-cohort-picker__stale"
          data-testid="cohort-stale-warning"
          role="alert"
        >
          ⚠ stale cohort — definition may have changed since last computation
        </div>
      )}
    </div>
  )
}

export default CohortPicker
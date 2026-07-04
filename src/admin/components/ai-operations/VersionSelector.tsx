/**
 * VersionSelector — REQ-044 US3 / FR-017 + AC-17.1/17.2 + EC-2.
 *
 * Renders 4 dimension dropdowns (prompt_fingerprint / rubric_version /
 * model / app_version) + a feature_area multi-select + the
 * "Comparing X vs Y" label surfaced when a non-default selection is
 * made (AC-17.4).
 *
 * Edge Case EC-2: each dimension surfaces the
 * ``unknownCount > 0`` count so the UI can render
 * "version unknown" explicitly for legacy rows; the value is NOT
 * silently folded into the baseline.
 */
import { useState } from 'react'
import type {
  VersionDimensionAvailability,
  VersionSelectorResponse,
} from '@/types/admin-ai-operations'

interface VersionSelectorProps {
  data: VersionSelectorResponse
  onChange: (
    selected: Record<string, string>,
    featureAreaFilter: string[],
  ) => void
}

const FEATURE_AREAS = [
  'resume_optimize',
  'mock_interview',
  'error_coach',
  'resume_render',
]

export function VersionSelector({ data, onChange }: VersionSelectorProps) {
  const initialSelection: Record<string, string> = {}
  data.dimensions.forEach((d: VersionDimensionAvailability) => {
    initialSelection[d.dimension] = d.knownValues[0] ?? ''
  })

  const [selected, setSelected] = useState<Record<string, string>>(initialSelection)
  const [featureAreaFilter, setFeatureAreaFilter] = useState<string[]>([])

  const update = (dimension: string, value: string) => {
    const next = { ...selected, [dimension]: value }
    setSelected(next)
    onChange(next, featureAreaFilter)
  }

  const toggleFeatureArea = (area: string) => {
    const next = featureAreaFilter.includes(area)
      ? featureAreaFilter.filter((a) => a !== area)
      : [...featureAreaFilter, area]
    setFeatureAreaFilter(next)
    onChange(selected, next)
  }

  const isComparing =
    Object.values(selected).some((v) => v !== '') ||
    featureAreaFilter.length > 0

  return (
    <div
      className="ac-ao-version-selector"
      data-testid="ai-operations-version-selector"
    >
      {isComparing && (
        <div
          className="ac-ao-version-selector__compare-label"
          data-testid="comparing-label"
        >
          Comparing {Object.values(selected).filter(Boolean).join(' · ')}{' '}
          {featureAreaFilter.length > 0 && (
            <span data-testid="comparing-feature-areas">
              · filter: {featureAreaFilter.join(', ')}
            </span>
          )}{' '}
          vs {data.baselineLabel}
        </div>
      )}

      <div className="ac-ao-version-selector__dimensions">
        {data.dimensions.map((d) => (
          <div
            key={d.dimension}
            className="ac-ao-version-selector__dimension"
            data-testid={`version-dim-${d.dimension}`}
          >
            <label
              htmlFor={`version-select-${d.dimension}`}
              className="ac-ao-version-selector__dimension-label"
            >
              {d.dimension}
            </label>
            <select
              id={`version-select-${d.dimension}`}
              data-testid={`version-select-${d.dimension}`}
              value={selected[d.dimension] ?? ''}
              onChange={(e) => update(d.dimension, e.target.value)}
            >
              <option value="">— any —</option>
              {d.knownValues.map((v) => (
                <option
                  key={v}
                  value={v}
                  data-testid={`version-option-${d.dimension}-${v}`}
                >
                  {v}
                </option>
              ))}
            </select>
            {d.unknownCount > 0 && (
              <div
                className="ac-ao-version-selector__unknown"
                data-testid={`version-unknown-${d.dimension}`}
                role="status"
              >
                ⚠ version unknown — {d.unknownCount} legacy row(s) lack this field
              </div>
            )}
          </div>
        ))}
      </div>

      <div
        className="ac-ao-version-selector__feature-area"
        data-testid="version-feature-area-filter"
      >
        <div className="ac-ao-version-selector__dimension-label">
          Feature area filter
        </div>
        <div className="ac-ao-version-selector__chips">
          {FEATURE_AREAS.map((area) => {
            const active = featureAreaFilter.includes(area)
            return (
              <button
                key={area}
                type="button"
                onClick={() => toggleFeatureArea(area)}
                className={
                  active
                    ? 'ac-ao-version-selector__chip ac-ao-version-selector__chip--active'
                    : 'ac-ao-version-selector__chip'
                }
                data-testid={`feature-area-chip-${area}`}
                data-active={active ? 'true' : 'false'}
              >
                {area}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default VersionSelector

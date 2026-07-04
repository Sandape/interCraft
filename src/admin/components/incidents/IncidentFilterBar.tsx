/**
 * IncidentFilterBar — REQ-044 US4 / FR-021 + AC-21.4.
 *
 * 7-dimension filter bar: severity / status / owner / feature_area /
 * journey / date range / trend. Each dimension is a native <select>
 * (no fancy combobox) so the surface is observable from the AC
 * matrix grep + Playwright. Filters are uncontrolled in this
 * iteration; the page-level state is the source of truth.
 */
import type {
  IncidentFilters,
  IncidentSeverity,
  IncidentStatus,
  IncidentTrend,
} from '@/types/admin-incidents'

interface IncidentFilterBarProps {
  filters: IncidentFilters
  onChange: (filters: IncidentFilters) => void
  owners: string[]
  featureAreas: string[]
  journeys: string[]
}

const SEVERITIES: (IncidentSeverity | 'all')[] = [
  'all',
  'P0',
  'P1',
  'P2',
  'P3',
]
const STATUSES: (IncidentStatus | 'all')[] = [
  'all',
  'open',
  'investigating',
  'resolved',
  'postmortem',
]
const TRENDS: (IncidentTrend | 'all')[] = ['all', 'rising', 'stable', 'declining']
const DATE_RANGES: IncidentFilters['dateRange'][] = ['24h', '7d', '30d', 'all']

export function IncidentFilterBar({
  filters,
  onChange,
  owners,
  featureAreas,
  journeys,
}: IncidentFilterBarProps) {
  const setFilter = <K extends keyof IncidentFilters>(
    key: K,
    value: IncidentFilters[K],
  ) => {
    onChange({ ...filters, [key]: value })
  }

  return (
    <div
      className="ic-filter-bar"
      data-testid="incident-filter-bar"
      role="toolbar"
      aria-label="Incident filters"
    >
      <label className="ic-filter" data-testid="severity-filter">
        <span className="ic-filter__label">Severity</span>
        <select
          value={filters.severity}
          onChange={(e) =>
            setFilter('severity', e.target.value as IncidentFilters['severity'])
          }
        >
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label className="ic-filter" data-testid="status-filter">
        <span className="ic-filter__label">Status</span>
        <select
          value={filters.status}
          onChange={(e) =>
            setFilter('status', e.target.value as IncidentFilters['status'])
          }
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label className="ic-filter" data-testid="owner-filter">
        <span className="ic-filter__label">Owner</span>
        <select
          value={filters.owner}
          onChange={(e) =>
            setFilter('owner', e.target.value as IncidentFilters['owner'])
          }
        >
          <option value="all">all</option>
          {owners.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </label>
      <label className="ic-filter" data-testid="feature-area-filter">
        <span className="ic-filter__label">Feature area</span>
        <select
          value={filters.featureArea}
          onChange={(e) =>
            setFilter('featureArea', e.target.value as IncidentFilters['featureArea'])
          }
        >
          <option value="all">all</option>
          {featureAreas.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </label>
      <label className="ic-filter" data-testid="journey-filter">
        <span className="ic-filter__label">Journey</span>
        <select
          value={filters.journey}
          onChange={(e) =>
            setFilter('journey', e.target.value as IncidentFilters['journey'])
          }
        >
          <option value="all">all</option>
          {journeys.map((j) => (
            <option key={j} value={j}>
              {j}
            </option>
          ))}
        </select>
      </label>
      <label className="ic-filter" data-testid="date-range-filter">
        <span className="ic-filter__label">Date range</span>
        <select
          value={filters.dateRange}
          onChange={(e) =>
            setFilter('dateRange', e.target.value as IncidentFilters['dateRange'])
          }
        >
          {DATE_RANGES.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </label>
      <label className="ic-filter" data-testid="trend-filter">
        <span className="ic-filter__label">Trend</span>
        <select
          value={filters.trend}
          onChange={(e) =>
            setFilter('trend', e.target.value as IncidentFilters['trend'])
          }
        >
          {TRENDS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}

export default IncidentFilterBar

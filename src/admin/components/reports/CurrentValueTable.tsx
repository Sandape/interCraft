/**
 * CurrentValueTable — REQ-044 US7 FR-030 AC-30.1/30.2.
 *
 * Renders the current_values list (live, as of "now"). Each row pairs
 * with the FrozenValueTable counterpart so the viewer shows side-by-side
 * frozen vs live. DataStatus badges use US6 QualityFlagsBadge.
 */
import { QualityFlagsBadge } from '@/admin/components/governance/QualityFlagsBadge'
import type { CurrentValue } from '@/types/admin-review-snapshots'

interface Props {
  values: CurrentValue[]
  fetchedAt: string
  'data-testid'?: string
}

export function CurrentValueTable({
  values,
  fetchedAt,
  'data-testid': testId,
}: Props) {
  return (
    <div
      className="ac-current-values"
      data-testid={testId ?? 'current-value-table'}
      data-current-at={fetchedAt}
    >
      <div className="ac-current-values__header">
        <span className="ac-current-values__title">Current values (live)</span>
        <span className="ac-current-values__timestamp">
          Current as of {fetchedAt}
        </span>
      </div>
      <table className="ac-current-values__table" role="table">
        <thead>
          <tr>
            <th scope="col">Metric</th>
            <th scope="col">Value</th>
            <th scope="col">Unit</th>
            <th scope="col">Captured</th>
            <th scope="col">Data Status</th>
          </tr>
        </thead>
        <tbody>
          {values.map((v) => (
            <tr key={v.metric_id} data-metric-id={v.metric_id}>
              <td>{v.metric_id}</td>
              <td className="ac-current-values__value">{v.value}</td>
              <td>{v.unit}</td>
              <td>{v.captured_at}</td>
              <td>
                <QualityFlagsBadge status={v.data_status} size="sm" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default CurrentValueTable
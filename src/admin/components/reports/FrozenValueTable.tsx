/**
 * FrozenValueTable — REQ-044 US7 FR-029 SC-012 + FR-030 AC-30.2.
 *
 * Renders the frozen_values list at the snapshot's capture time.
 * Each row carries the metric_id / value / unit / captured_at /
 * data_status badge (US6 QualityFlagsBadge reused).
 */
import { QualityFlagsBadge } from '@/admin/components/governance/QualityFlagsBadge'
import type { FrozenValue } from '@/types/admin-review-snapshots'

interface Props {
  values: FrozenValue[]
  frozenAt: string
  'data-testid'?: string
}

export function FrozenValueTable({
  values,
  frozenAt,
  'data-testid': testId,
}: Props) {
  return (
    <div
      className="ac-frozen-values"
      data-testid={testId ?? 'frozen-value-table'}
      data-frozen-at={frozenAt}
    >
      <div className="ac-frozen-values__header">
        <span className="ac-frozen-values__title">Frozen values</span>
        <span className="ac-frozen-values__timestamp">
          Frozen at {frozenAt}
        </span>
      </div>
      <table className="ac-frozen-values__table" role="table">
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
              <td className="ac-frozen-values__value">{v.value}</td>
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

export default FrozenValueTable
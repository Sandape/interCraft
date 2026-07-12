/**
 * REQ-061 T122 — point → milestone timeline for a task.
 */
export interface PointCostMilestoneRow {
  milestone?: string
  occurred_at?: string
  points?: number | null
  cost_rmb?: string | null
}

export interface PointCostTimelineProps {
  milestones?: PointCostMilestoneRow[]
  pointSettled?: number
  unavailable?: boolean
  loading?: boolean
}

function displayPoints(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'unknown'
  return String(value)
}

function displayCost(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return 'unknown'
  return value
}

export function PointCostTimeline({
  milestones = [],
  pointSettled,
  unavailable,
  loading,
}: PointCostTimelineProps) {
  return (
    <section
      className="rounded border border-surface-border p-3"
      data-testid="point-cost-timeline"
    >
      <h3 className="mb-2 text-sm font-semibold">点数 / 里程碑时间线</h3>
      {typeof pointSettled === 'number' && (
        <p className="mb-2 text-xs text-ink-3" data-testid="point-settled">
          settled={pointSettled}
        </p>
      )}
      {loading && <p className="text-xs text-ink-3">加载中…</p>}
      {unavailable ? (
        <p className="text-xs text-ink-3" data-testid="point-cost-timeline-unavailable">
          点数时间线不可用
        </p>
      ) : (
        <ol className="space-y-2 text-sm">
          {milestones.map((item, idx) => (
            <li
              key={`${item.milestone ?? 'm'}-${idx}`}
              data-testid={`point-cost-milestone-${idx}`}
              data-points={displayPoints(item.points)}
              data-cost={displayCost(item.cost_rmb)}
            >
              <div className="font-medium">
                {item.milestone ?? 'milestone'} · points={displayPoints(item.points)} · cost=
                {displayCost(item.cost_rmb)}
              </div>
              {item.occurred_at && (
                <div className="text-xs text-ink-3">{item.occurred_at}</div>
              )}
            </li>
          ))}
          {!loading && milestones.length === 0 && (
            <li className="text-ink-3">暂无点数事件</li>
          )}
        </ol>
      )}
    </section>
  )
}

export default PointCostTimeline

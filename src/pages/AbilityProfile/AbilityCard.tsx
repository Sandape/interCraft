/** AbilityCard — single dimension card with label, scores, trend indicator. */
import { useNavigate } from 'react-router-dom'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { DashboardDimension } from '@/api/abilityProfileClient'
import { cn } from '@/lib/utils'

interface Props {
  dimension: DashboardDimension
  onEdit?: () => void
  readOnly?: boolean
}

export default function AbilityCard({ dimension: d, onEdit, readOnly }: Props) {
  const navigate = useNavigate()

  const trendIcon =
    d.trend === 'up' ? (
      <TrendingUp className="h-3.5 w-3.5" />
    ) : d.trend === 'down' ? (
      <TrendingDown className="h-3.5 w-3.5" />
    ) : (
      <Minus className="h-3.5 w-3.5" />
    )

  const trendColor =
    d.trend === 'up'
      ? 'text-emerald-500'
      : d.trend === 'down'
        ? 'text-red-500'
        : 'text-ink-3'

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/ability-profile/${d.key}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(`/ability-profile/${d.key}`)
        }
      }}
      className="flex items-center justify-between p-3 rounded-lg border border-surface-border dark:border-dark-surface-border hover:border-brand-500/30 transition-colors cursor-pointer"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-ink-1">{d.label_zh}</span>
          {d.self_assessed_score !== null &&
            d.self_assessed_score !== d.actual_score && (
              <span className="text-2xs text-ink-3">
                系统 {d.actual_score} / 自评 {d.self_assessed_score}
              </span>
            )}
        </div>
        <div className="flex items-center gap-3 mt-1">
          <span className="text-lg font-semibold text-ink-1 tabular-nums">
            {d.actual_score}
          </span>
          <span className="text-2xs text-ink-3">/ {d.ideal_score}</span>
          <span className={cn('flex items-center gap-0.5 text-2xs', trendColor)}>
            {trendIcon}
            {d.trend === 'up' ? '上升' : d.trend === 'down' ? '下降' : '平稳'}
          </span>
        </div>
      </div>
      {!readOnly && onEdit && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onEdit()
          }}
          className="text-2xs text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 font-medium px-2 py-1 rounded hover:bg-brand-50 dark:hover:bg-brand-500/10 transition-colors"
        >
          自评
        </button>
      )}
    </div>
  )
}

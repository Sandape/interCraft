interface FunnelStep {
  label: string
  count: number
  color: string
}

const DEFAULT_COLORS = [
  'bg-brand-500',
  'bg-blue-400',
  'bg-amber-400',
  'bg-emerald-400',
  'bg-red-400',
]

export function FunnelChart({ data }: { data: FunnelStep[] }) {
  const max = Math.max(...data.map((d) => d.count), 1)

  return (
    <div className="space-y-2">
      {data.map((step, i) => {
        const pct = Math.round((step.count / max) * 100)
        return (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs text-ink-2 w-16 text-right flex-shrink-0">{step.label}</span>
            <div className="flex-1 h-6 bg-surface-muted dark:bg-dark-surface-muted rounded overflow-hidden">
              <div
                className={`h-full rounded transition-all duration-500 ${step.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length]}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs font-medium text-ink-1 w-8 tabular-nums">{step.count}</span>
          </div>
        )
      })}
    </div>
  )
}

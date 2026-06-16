/** TimelineChart — recharts LineChart showing ability score history over time. */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import type { DimensionHistoryPoint } from '@/api/abilityProfileClient'

interface Props {
  history: DimensionHistoryPoint[]
  dimensionLabel?: string
}

export default function TimelineChart({ history, dimensionLabel }: Props) {
  if (!history || history.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-ink-3">
        暂无历史数据
      </div>
    )
  }

  const data = history.map((h) => ({
    date: h.date,
    actual: h.actual_score,
    ideal: h.ideal_score,
  }))

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: '#94a3b8' }}
          tickLine={false}
        />
        <YAxis
          domain={[0, 10]}
          tick={{ fontSize: 11, fill: '#94a3b8' }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={{
            fontSize: 12,
            borderRadius: 8,
            border: '1px solid #e2e8f0',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="ideal"
          name="理想分数"
          stroke="rgba(148,163,184,0.5)"
          strokeDasharray="4 4"
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="actual"
          name="实际分数"
          stroke="rgb(59,130,246)"
          strokeWidth={2}
          dot={{ r: 3, fill: 'white', stroke: 'rgb(59,130,246)', strokeWidth: 2 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

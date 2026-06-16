/** RadarChart — recharts-based radar/spider chart for ability dimensions. */
import {
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { DashboardDimension } from '@/api/abilityProfileClient'

interface Props {
  dimensions: DashboardDimension[]
  showSelfAssessed?: boolean
}

export default function AbilityRadarChart({ dimensions, showSelfAssessed = false }: Props) {
  if (!dimensions.length) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-ink-3">
        暂无能力数据 — 完成面试或自评后生成
      </div>
    )
  }

  const chartData = dimensions.map((d) => ({
    dimension: d.label_zh,
    actual: d.actual_score,
    ideal: d.ideal_score,
    selfAssessed: d.self_assessed_score ?? undefined,
  }))

  return (
    <ResponsiveContainer width="100%" height={360}>
      <RechartsRadar data={chartData} cx="50%" cy="50%" outerRadius="70%">
        <PolarGrid stroke="rgba(148,163,184,0.2)" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fontSize: 12, fill: 'var(--tw-ink-2, #64748b)' }}
        />
        <PolarRadiusAxis
          angle={90}
          domain={[0, 10]}
          tick={{ fontSize: 10, fill: 'var(--tw-ink-3, #94a3b8)' }}
        />
        <Radar
          name="理想"
          dataKey="ideal"
          stroke="rgba(148,163,184,0.5)"
          fill="rgba(148,163,184,0.05)"
          strokeDasharray="4 4"
          fillOpacity={0}
        />
        <Radar
          name="实际"
          dataKey="actual"
          stroke="rgb(59,130,246)"
          fill="rgba(59,130,246,0.15)"
          fillOpacity={0.3}
        />
        {showSelfAssessed && (
          <Radar
            name="自评"
            dataKey="selfAssessed"
            stroke="rgb(34,197,94)"
            fill="rgba(34,197,94,0.1)"
            fillOpacity={0.2}
          />
        )}
        <Legend
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          iconType="circle"
        />
      </RechartsRadar>
    </ResponsiveContainer>
  )
}

/** AbilityProfileDetail — single dimension detail page with timeline chart. */
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useAbilityDashboard } from '@/pages/AbilityProfile/hooks/queries/useAbilityProfile'
import { useSelfAssess } from '@/pages/AbilityProfile/hooks/mutations/useSelfAssess'
import TimelineChart from '@/pages/AbilityProfile/TimelineChart'
import AbilityDetail from '@/pages/AbilityProfile/AbilityDetail'
import { useState } from 'react'
import type { DashboardDimension } from '@/api/abilityProfileClient'

export default function AbilityProfileDetail() {
  const { abilityKey } = useParams<{ abilityKey: string }>()
  const navigate = useNavigate()
  const { data, isLoading } = useAbilityDashboard()
  const selfAssess = useSelfAssess()
  const [showAssess, setShowAssess] = useState(false)

  const dimensions = data?.data?.dimensions ?? []
  const dim = dimensions.find((d) => d.key === abilityKey)

  if (isLoading) {
    return (
      <div className="px-8 py-6 max-w-7xl mx-auto flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 text-ink-3 animate-spin" />
      </div>
    )
  }

  if (!dim) {
    return (
      <div className="px-8 py-6 max-w-7xl mx-auto text-center py-24">
        <p className="text-sm text-ink-3">维度未找到</p>
        <Button variant="secondary" onClick={() => navigate('/ability-profile')} className="mt-4">
          返回画像页面
        </Button>
      </div>
    )
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      <button
        onClick={() => navigate('/ability-profile')}
        className="flex items-center gap-1 text-sm text-ink-3 hover:text-ink-1 mb-4 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        返回画像页面
      </button>

      <div className="mb-4 grid gap-3 md:grid-cols-2">
        <Card className="p-4" data-testid="verified-score-panel">
          <h3 className="text-sm font-semibold">已验证评分</h3>
          <p className="mt-1 text-sm">当前 {dim.actual_score}</p>
        </Card>
        <Card className="p-4" data-testid="ai-insight-panel">
          <h3 className="text-sm font-semibold">AI 洞察</h3>
          <p className="mt-1 text-xs text-ink-3">与确定性评分独立；失败不影响已验证分。</p>
          {(data as { data?: { ai_insight?: { task_id?: string; status?: string } } } | undefined)?.data?.ai_insight?.task_id && (
            <button
              type="button"
              className="mt-2 text-xs text-brand-600 underline"
              data-testid="ai-insight-task-link"
              onClick={() =>
                navigate(
                  `/ai-tasks/${encodeURIComponent(
                    (data as { data: { ai_insight: { task_id: string } } }).data.ai_insight.task_id,
                  )}`,
                )
              }
            >
              查看洞察任务
            </button>
          )}
        </Card>
      </div>

      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">{dim.label_zh}</h1>
          <p className="text-sm text-ink-3 mt-1">
            当前分数: {dim.actual_score} / 目标: {dim.ideal_score}
            {dim.trend === 'up' ? ' · 上升趋势' : dim.trend === 'down' ? ' · 下降趋势' : ' · 平稳'}
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowAssess(true)}>
          自评
        </Button>
      </div>

      {/* Score overview */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <Card className="p-4 text-center">
          <div className="text-2xs text-ink-3 mb-1">当前分数</div>
          <div className="text-2xl font-semibold text-brand-600 tabular-nums">{dim.actual_score}</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xs text-ink-3 mb-1">目标分数</div>
          <div className="text-2xl font-semibold text-ink-1 tabular-nums">{dim.ideal_score}</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xs text-ink-3 mb-1">差距</div>
          <div className="text-2xl font-semibold text-amber-600 tabular-nums">
            {(dim.ideal_score - dim.actual_score).toFixed(1)}
          </div>
        </Card>
      </div>

      {/* Timeline chart */}
      <Card className="p-6">
        <CardHeader
          title="成长轨迹"
          description="该维度分数随时间的变化"
        />
        <TimelineChart history={dim.history} dimensionLabel={dim.label_zh} />
      </Card>

      {/* Self-assessment modal */}
      {showAssess && (
        <AbilityDetail
          label={dim.label_zh}
          currentScore={dim.actual_score}
          idealScore={dim.ideal_score}
          onSubmit={(score, notes) => {
            selfAssess.mutate({ key: dim.key, score, notes })
            setShowAssess(false)
          }}
          onClose={() => setShowAssess(false)}
        />
      )}
    </div>
  )
}

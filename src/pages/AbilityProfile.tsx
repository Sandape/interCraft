/** AbilityProfile — dashboard page with radar chart and ability list. */
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Share2, Download, Loader2, Target } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useAbilityDashboard } from '@/pages/AbilityProfile/hooks/queries/useAbilityProfile'
import { useSelfAssess } from '@/pages/AbilityProfile/hooks/mutations/useSelfAssess'
import { useExportPdf } from '@/pages/AbilityProfile/hooks/mutations/useExportPDF'
import AbilityRadarChart from '@/pages/AbilityProfile/RadarChart'
import AbilityCard from '@/pages/AbilityProfile/AbilityCard'
import AbilityDetail from '@/pages/AbilityProfile/AbilityDetail'
import ShareDialog from '@/pages/AbilityProfile/ShareDialog'
import type { DashboardDimension } from '@/api/abilityProfileClient'

function hasAssessmentData(dimensions: DashboardDimension[]): boolean {
  return dimensions.some(
    (d) =>
      d.actual_score > 0 ||
      d.self_assessed_score !== null ||
      (d.history?.length ?? 0) > 0 ||
      d.source === 'interview' ||
      d.source === 'coach',
  )
}

export default function AbilityProfile() {
  const navigate = useNavigate()
  const { data, isLoading, isError, refetch } = useAbilityDashboard()
  const selfAssess = useSelfAssess()
  const exportPdf = useExportPdf()
  const [selectedDim, setSelectedDim] = useState<DashboardDimension | null>(null)
  const [showShare, setShowShare] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  const dimensions = data?.data?.dimensions ?? []
  const hasSelfAssessed = dimensions.some((d) => d.self_assessed_score !== null)
  const isEmpty = !hasAssessmentData(dimensions)

  if (isLoading) {
    return (
      <div className="px-8 py-6 max-w-7xl mx-auto flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 text-ink-3 animate-spin" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="px-8 py-6 max-w-7xl mx-auto text-center py-24">
        <p className="text-sm text-ink-3 mb-4">加载能力画像失败</p>
        <Button variant="secondary" onClick={() => refetch()}>
          重试
        </Button>
      </div>
    )
  }

  const handleExport = () => {
    setExportError(null)
    exportPdf.mutate(undefined, {
      onError: (err) => {
        setExportError(err instanceof Error ? err.message : '导出失败，请稍后重试')
      },
    })
  }

  return (
    <div className="px-4 py-5 sm:px-6 lg:px-8 lg:py-6 max-w-7xl mx-auto">
      <div className="flex flex-col items-stretch gap-4 mb-6 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">能力画像</h1>
          <p className="text-sm text-ink-3 mt-1">6 维度能力雷达图，追踪成长趋势</p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:items-center">
          <Button
            variant="secondary"
            className="w-full sm:w-auto"
            leftIcon={<Share2 className="h-3.5 w-3.5" />}
            onClick={() => setShowShare(true)}
            disabled={isEmpty}
          >
            分享
          </Button>
          <Button
            variant="primary"
            className="w-full sm:w-auto"
            leftIcon={<Download className="h-3.5 w-3.5" />}
            onClick={handleExport}
            loading={exportPdf.isPending}
            disabled={isEmpty}
          >
            导出 PDF
          </Button>
        </div>
      </div>

      {exportError && (
        <div className="mb-4 text-sm text-red-600 dark:text-red-400">{exportError}</div>
      )}

      {/* REQ-061 T097 — verified score vs AI insight are independent */}
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        <Card className="p-4" data-testid="verified-score-panel">
          <h3 className="text-sm font-semibold text-ink-1">已验证评分</h3>
          <p className="mt-1 text-xs text-ink-3">
            来自面试/自评等确定性结果，不依赖 AI 洞察任务状态。
          </p>
          <p className="mt-2 text-sm text-ink-2">
            状态：{data?.data?.verified_score_status === 'ready' ? '就绪' : '暂无'}
          </p>
        </Card>
        <Card className="p-4" data-testid="ai-insight-panel">
          <h3 className="text-sm font-semibold text-ink-1">AI 洞察</h3>
          {(() => {
            const insight = data?.data?.ai_insight
            if (!insight) {
              return <p className="mt-1 text-xs text-ink-3">暂无 AI 洞察任务。</p>
            }
            return (
              <div className="mt-2 space-y-2 text-sm">
                <p>状态：{insight.status}</p>
                {insight.user_summary && <p className="text-amber-800">{insight.user_summary}</p>}
                {insight.task_id && (
                  <Link
                    to={`/ai-tasks/${encodeURIComponent(insight.task_id)}`}
                    className="text-brand-600 underline"
                    data-testid="ai-insight-task-link"
                  >
                    查看洞察任务
                  </Link>
                )}
                {insight.available_actions.includes('system_failure_retry') && (
                  <Button
                    variant="secondary"
                    size="sm"
                    data-testid="ai-insight-retry"
                    onClick={() => navigate(`/ai-tasks/${encodeURIComponent(insight.task_id)}`)}
                  >
                    重试洞察
                  </Button>
                )}
              </div>
            )
          })()}
        </Card>
      </div>

      {isEmpty ? (
        <Card className="p-6 text-center sm:p-12">
          <Target className="h-12 w-12 text-ink-muted mx-auto mb-4" />
          <h3 className="text-base font-medium text-ink-1 mb-2">暂无能力数据</h3>
          <p className="text-sm text-ink-3 mb-4">
            完成模拟面试或进行自评后，你的能力画像将在这里展示
          </p>
          <div className="flex items-center justify-center gap-2">
            <Button variant="primary" onClick={() => navigate('/interview')}>
              开始面试
            </Button>
            {dimensions[0] && (
              <Button variant="secondary" onClick={() => setSelectedDim(dimensions[0])}>
                先做自评
              </Button>
            )}
          </div>
        </Card>
      ) : (
        <>
          <Card className="p-6 mb-4">
            <CardHeader
              title="能力雷达对比"
              description="蓝色 = 系统评分 · 绿色 = 自评 · 灰色虚线 = 目标"
              action={
                <Badge variant="brand" leftIcon={<Target className="h-2.5 w-2.5" />}>
                  {dimensions.length} 维度
                </Badge>
              }
            />
            <AbilityRadarChart dimensions={dimensions} showSelfAssessed={hasSelfAssessed} />
          </Card>

          <div className="space-y-2">
            <h3 className="text-sm font-medium text-ink-1">能力列表</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {dimensions.map((d) => (
                <AbilityCard
                  key={d.key}
                  dimension={d}
                  onEdit={() => setSelectedDim(d)}
                />
              ))}
            </div>
          </div>
        </>
      )}

      {selectedDim && (
        <AbilityDetail
          label={selectedDim.label_zh}
          currentScore={selectedDim.self_assessed_score ?? selectedDim.actual_score}
          idealScore={selectedDim.ideal_score}
          onSubmit={(score, notes) => {
            selfAssess.mutate({ key: selectedDim.key, score, notes })
            setSelectedDim(null)
          }}
          onClose={() => setSelectedDim(null)}
        />
      )}

      {showShare && <ShareDialog onClose={() => setShowShare(false)} />}
    </div>
  )
}

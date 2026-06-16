/** AbilityProfile — dashboard page with radar chart and ability list. */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Share2, Download, Loader2, Target } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useAbilityDashboard } from '@/pages/AbilityProfile/hooks/queries/useAbilityProfile'
import { useSelfAssess } from '@/pages/AbilityProfile/hooks/mutations/useSelfAssess'
import { useTriggerExport } from '@/pages/AbilityProfile/hooks/mutations/useExportPDF'
import AbilityRadarChart from '@/pages/AbilityProfile/RadarChart'
import AbilityCard from '@/pages/AbilityProfile/AbilityCard'
import AbilityDetail from '@/pages/AbilityProfile/AbilityDetail'
import ShareDialog from '@/pages/AbilityProfile/ShareDialog'
import type { DashboardDimension } from '@/api/abilityProfileClient'

export default function AbilityProfile() {
  const navigate = useNavigate()
  const { data, isLoading } = useAbilityDashboard()
  const selfAssess = useSelfAssess()
  const triggerExport = useTriggerExport()
  const [selectedDim, setSelectedDim] = useState<DashboardDimension | null>(null)
  const [showShare, setShowShare] = useState(false)

  const dimensions = data?.data?.dimensions ?? []
  const hasSystemScores = dimensions.some((d) => d.self_assessed_score !== null)

  if (isLoading) {
    return (
      <div className="px-8 py-6 max-w-7xl mx-auto flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 text-ink-3 animate-spin" />
      </div>
    )
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">能力画像</h1>
          <p className="text-sm text-ink-3 mt-1">
            6 维度能力雷达图，追踪成长趋势
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" leftIcon={<Share2 className="h-3.5 w-3.5" />} onClick={() => setShowShare(true)}>
            分享
          </Button>
          <Button
            variant="primary"
            leftIcon={<Download className="h-3.5 w-3.5" />}
            onClick={() => triggerExport.mutate()}
            loading={triggerExport.isPending}
          >
            导出 PDF
          </Button>
        </div>
      </div>

      {/* Empty state */}
      {dimensions.length === 0 ? (
        <Card className="p-12 text-center">
          <Target className="h-12 w-12 text-ink-muted mx-auto mb-4" />
          <h3 className="text-base font-medium text-ink-1 mb-2">暂无能力数据</h3>
          <p className="text-sm text-ink-3 mb-4">
            完成模拟面试或进行自评后，你的能力画像将在这里展示
          </p>
          <Button variant="primary" onClick={() => navigate('/interview/new')}>
            开始面试
          </Button>
        </Card>
      ) : (
        <>
          {/* Radar Chart */}
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
            <AbilityRadarChart dimensions={dimensions} showSelfAssessed={hasSystemScores} />
          </Card>

          {/* Ability List */}
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

      {/* Self-assessment modal */}
      {selectedDim && (
        <AbilityDetail
          label={selectedDim.label_zh}
          currentScore={selectedDim.actual_score}
          idealScore={selectedDim.ideal_score}
          onSubmit={(score, notes) => {
            selfAssess.mutate({ key: selectedDim.key, score })
            setSelectedDim(null)
          }}
          onClose={() => setSelectedDim(null)}
        />
      )}

      {/* Share dialog */}
      {showShare && <ShareDialog onClose={() => setShowShare(false)} />}
    </div>
  )
}

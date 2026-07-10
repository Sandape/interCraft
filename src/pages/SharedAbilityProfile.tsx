/** SharedAbilityProfile — public read-only shared profile page (no PIN — 024). */
import { useParams } from 'react-router-dom'
import { Loader2, Eye } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { useSharedProfile } from '@/pages/AbilityProfile/hooks/queries/useAbilityProfile'
import AbilityRadarChart from '@/pages/AbilityProfile/RadarChart'

export default function SharedAbilityProfile() {
  const { shareToken } = useParams<{ shareToken: string }>()
  const { data, isLoading, error } = useSharedProfile(shareToken!)

  if (error) {
    const status = (error as { status?: number })?.status
    const message =
      status === 410
        ? '该分享链接已过期'
        : status === 403
          ? '该分享链接已被撤销'
          : '该分享链接不存在、已过期或已被撤销'

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
        <Card className="p-6 text-center">
          <h2 className="text-base font-semibold text-ink-1 mb-2">无法访问</h2>
          <p className="text-sm text-ink-3">{message}</p>
        </Card>
      </div>
    )
  }

  if (isLoading || !data?.data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <Loader2 className="h-6 w-6 text-ink-3 animate-spin" />
      </div>
    )
  }

  const profile = data.data
  const dimensions = profile.dimensions.map((d) => ({
    key: d.key,
    label_zh: d.label_zh,
    actual_score: d.actual_score,
    ideal_score: d.ideal_score ?? 10,
    self_assessed_score: null,
    source: 'system',
    trend: 'stable' as const,
    history: [],
  }))

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="text-center mb-6">
          <h1 className="text-xl font-semibold text-ink-1">
            {profile.owner.name} 的能力画像
          </h1>
          {profile.owner.title && (
            <p className="text-sm text-ink-3 mt-1">{profile.owner.title}</p>
          )}
          <div className="flex items-center justify-center gap-1 mt-2 text-2xs text-ink-4">
            <Eye className="h-3 w-3" />
            只读分享 · {new Date(profile.generated_at).toLocaleDateString()}
          </div>
        </div>

        <Card className="p-6 mb-4">
          <AbilityRadarChart dimensions={dimensions} />
        </Card>

        <Card className="p-4">
          <div className="divide-y divide-surface-border dark:divide-dark-surface-border">
            {profile.dimensions.map((d) => (
              <div key={d.key} className="flex items-center justify-between py-2">
                <span className="text-sm text-ink-1">{d.label_zh}</span>
                <span className="text-sm font-semibold text-brand-600 tabular-nums">
                  {d.actual_score}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <div className="text-center mt-6 text-2xs text-ink-4">由 InterCraft 生成</div>
      </div>
    </div>
  )
}

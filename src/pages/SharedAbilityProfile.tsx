/** SharedAbilityProfile — public read-only shared profile page. */
import { useParams } from 'react-router-dom'
import { Loader2, Lock, Eye } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useSharedProfile } from '@/pages/AbilityProfile/hooks/queries/useAbilityProfile'
import AbilityRadarChart from '@/pages/AbilityProfile/RadarChart'
import { useState } from 'react'

export default function SharedAbilityProfile() {
  const { shareToken } = useParams<{ shareToken: string }>()
  const [pin, setPin] = useState('')
  const [submittedPin, setSubmittedPin] = useState<string | undefined>(undefined)

  const { data, isLoading, error } = useSharedProfile(shareToken!, submittedPin)

  // If PIN is required (401), show PIN input
  if (error && (error as any)?.status === 401) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
        <Card className="p-6 w-full max-w-sm">
          <div className="text-center mb-4">
            <Lock className="h-8 w-8 text-ink-3 mx-auto mb-2" />
            <h2 className="text-base font-semibold text-ink-1">需要 PIN 码</h2>
            <p className="text-xs text-ink-3 mt-1">该分享链接受 PIN 保护</p>
          </div>
          <input
            type="text"
            maxLength={4}
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
            placeholder="输入 4 位 PIN"
            className="w-full text-center text-lg border border-surface-border rounded-lg p-2 mb-3 bg-transparent text-ink-1 tracking-widest"
            autoFocus
          />
          <Button variant="primary" onClick={() => setSubmittedPin(pin)} className="w-full">
            验证
          </Button>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
        <Card className="p-6 text-center">
          <h2 className="text-base font-semibold text-ink-1 mb-2">无法访问</h2>
          <p className="text-sm text-ink-3">
            该分享链接不存在、已过期或已被撤销
          </p>
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
    ideal_score: 10,
    self_assessed_score: null,
    source: 'system',
    trend: 'stable' as const,
    history: [],
  }))

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Header */}
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

        {/* Radar chart */}
        <Card className="p-6 mb-4">
          <AbilityRadarChart dimensions={dimensions} />
        </Card>

        {/* Simple list */}
        <Card className="p-4">
          <div className="divide-y divide-surface-border dark:divide-dark-surface-border">
            {profile.dimensions.map((d) => (
              <div key={d.key} className="flex items-center justify-between py-2">
                <span className="text-sm text-ink-1">{d.label_zh}</span>
                <span className="text-sm font-semibold text-brand-600 tabular-nums">{d.actual_score}</span>
              </div>
            ))}
          </div>
        </Card>

        <div className="text-center mt-6 text-2xs text-ink-4">
          由 InterCraft 生成
        </div>
      </div>
    </div>
  )
}

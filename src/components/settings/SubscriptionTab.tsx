/**
 * REQ-061 (US8 / T055) — Settings subscription tab: Pro experience + points.
 *
 * No Free/Pro/Enterprise upgrade CTA, no monthly-token UI, no RMB/purchase.
 */
import { Link } from 'react-router-dom'
import { Crown, Sparkles, Calendar, RefreshCw, Coins } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useAIPointAccount } from '@/hooks/queries/useAIPoints'
import type { PointBucket } from '@/types/ai-metering'

const BUCKET_LABELS: Record<PointBucket['bucket_type'], string> = {
  daily_experience: '每日体验',
  compensation: '补偿点数',
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN')
}

export default function SubscriptionTab() {
  const { data, isLoading, isError, error, refetch, isFetching } = useAIPointAccount()

  if (isLoading) {
    return <Card className="p-5 text-center text-sm text-ink-3">加载中...</Card>
  }

  if (isError || !data) {
    return (
      <Card className="p-5 space-y-3" data-testid="subscription-tab-error">
        <p className="text-sm text-ink-2">体验点数加载失败，请稍后重试。</p>
        <p className="text-xs text-ink-3">
          {error instanceof Error ? error.message : '网络或服务暂时不可用'}
        </p>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />}
          onClick={() => refetch()}
          disabled={isFetching}
        >
          重试
        </Button>
      </Card>
    )
  }

  return (
    <div className="space-y-4" data-testid="subscription-tab-pro">
      <Card className="p-6 bg-gradient-to-br from-brand-50/50 to-surface dark:from-brand-500/5 dark:to-dark-surface border-brand-200/60 dark:border-brand-500/20">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-md bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
              <Crown className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-base font-semibold text-ink-1">{data.plan_label}</h2>
                <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
                  {data.experience_badge}
                </Badge>
              </div>
              <p className="text-xs text-ink-3 mt-0.5">
                内测体验权益 · 非购买关系 · 每日发放 {data.daily_grant_amount.toLocaleString()} 点
              </p>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<RefreshCw className={`h-3.5 w-3.5 ${isFetching ? 'animate-spin' : ''}`} />}
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label="刷新点数"
          >
            刷新
          </Button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-4 border-t border-surface-border dark:border-dark-surface-border">
          <div>
            <div className="text-2xs text-ink-3">可用点数</div>
            <div className="text-base font-semibold text-ink-1 mt-0.5 tabular-nums">
              {data.available.toLocaleString()}
            </div>
          </div>
          <div>
            <div className="text-2xs text-ink-3">预留中</div>
            <div className="text-base font-semibold text-ink-1 mt-0.5 tabular-nums">
              {data.reserved.toLocaleString()}
            </div>
          </div>
          <div>
            <div className="text-2xs text-ink-3">并行任务上限</div>
            <div className="text-base font-semibold text-ink-1 mt-0.5 tabular-nums">
              {data.parallel_ai_task_limit}
            </div>
          </div>
          <div>
            <div className="text-2xs text-ink-3 flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              最近到期
            </div>
            <div className="text-sm font-medium text-ink-1 mt-0.5">
              {formatDateTime(data.next_expiry)}
            </div>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader title="点数桶" />
        {data.buckets.length === 0 ? (
          <p className="text-sm text-ink-3">暂无有效点数桶。跨日零点后将按配置发放当日体验点。</p>
        ) : (
          <ul className="space-y-2">
            {data.buckets.map((bucket) => (
              <li
                key={bucket.bucket_id}
                className="flex items-center justify-between gap-3 p-3 rounded-md border border-surface-border dark:border-dark-surface-border"
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium text-ink-1">
                    {BUCKET_LABELS[bucket.bucket_type] ?? bucket.bucket_type}
                  </div>
                  <div className="text-2xs text-ink-3 mt-0.5">
                    到期 {formatDateTime(bucket.expires_at)}
                    {bucket.business_date ? ` · 业务日 ${bucket.business_date}` : ''}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-semibold tabular-nums text-ink-1">
                    {bucket.available.toLocaleString()} 可用
                  </div>
                  <div className="text-2xs text-ink-3 tabular-nums">
                    {bucket.reserved.toLocaleString()} 预留
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-medium text-ink-1 flex items-center gap-1.5">
              <Coins className="h-4 w-4 text-brand-500" />
              点数明细与预算
            </div>
            <p className="text-xs text-ink-3 mt-1">
              查看发放、预留、扣除、退回与任务关联，历史保留 {data.history_days} 天。
            </p>
          </div>
          <Link
            to="/ai-points"
            className="text-sm text-brand-600 dark:text-brand-300 hover:underline shrink-0"
            data-testid="subscription-tab-ai-points-link"
          >
            打开点数中心
          </Link>
        </div>
      </Card>
    </div>
  )
}

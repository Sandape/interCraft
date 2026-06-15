import { useState, useEffect } from 'react'
import { Crown, Sparkles, Calendar, Check, RefreshCw } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { accountApi, type CurrentSubscription, type SubscriptionPlan } from '@/api/account'

const PLAN_LABELS: Record<string, string> = {
  free: '免费版',
  pro: 'Pro 会员',
  enterprise: 'Enterprise',
}

export default function SubscriptionTab() {
  const [subscription, setSubscription] = useState<CurrentSubscription | null>(null)
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      accountApi.getCurrentSubscription(),
      accountApi.listPlans(),
    ]).then(([sub, planData]) => {
      setSubscription(sub)
      setPlans(planData.plans)
      setLoading(false)
    })
  }, [])

  if (loading) {
    return <Card className="p-5 text-center text-sm text-ink-3">加载中...</Card>
  }

  const isPro = subscription?.plan === 'pro'
  const isEnterprise = subscription?.plan === 'enterprise'

  return (
    <div className="space-y-4">
      <Card className="p-6 bg-gradient-to-br from-brand-50/50 to-surface dark:from-brand-500/5 dark:to-dark-surface border-brand-200/60 dark:border-brand-500/20">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-md bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
              <Crown className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-ink-1">{PLAN_LABELS[subscription?.plan ?? 'free']}</h2>
                {isPro && (
                  <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
                    当前
                  </Badge>
                )}
              </div>
              {subscription?.reset_date && (
                <div className="text-xs text-ink-3 mt-0.5 flex items-center gap-1.5">
                  <Calendar className="h-3 w-3" />
                  重置日期 {new Date(subscription.reset_date).toLocaleDateString('zh-CN')}
                </div>
              )}
            </div>
          </div>
          {!isEnterprise && (
            <Button variant="primary" size="sm">
              升级到 {isPro ? 'Enterprise' : 'Pro'}
            </Button>
          )}
        </div>
        <div className="grid grid-cols-3 gap-3 pt-4 border-t border-surface-border dark:border-dark-surface-border">
          <div>
            <div className="text-2xs text-ink-3">月度 Token 配额</div>
            <div className="text-base font-semibold text-ink-1 mt-0.5">{(subscription?.monthly_token_quota ?? 0).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-2xs text-ink-3">已使用</div>
            <div className="text-base font-semibold text-ink-1 mt-0.5">{(subscription?.monthly_token_used ?? 0).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-2xs text-ink-3">剩余</div>
            <div className="text-base font-semibold text-ink-1 mt-0.5">{(subscription?.monthly_token_remaining ?? 0).toLocaleString()}</div>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader title="本月用量" />
        <div className="space-y-3">
          <UsageBar
            label="Token 使用量"
            used={subscription?.monthly_token_used ?? 0}
            total={subscription?.monthly_token_quota ?? 1}
          />
          <p className="text-xs text-ink-3">
            {subscription?.can_start_interview
              ? '配额充足，可正常开始面试'
              : '配额已用尽，请升级方案或等待下月重置'}
          </p>
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader title="可用方案" />
        <div className="space-y-2">
          {plans.map((p) => (
            <div
              key={p.plan}
              className="flex items-center justify-between p-3 rounded-md border border-surface-border dark:border-dark-surface-border"
            >
              <div>
                <div className="text-sm font-medium text-ink-1">{PLAN_LABELS[p.plan] || p.plan}</div>
                <div className="text-2xs text-ink-3 mt-0.5">{p.monthly_token_quota.toLocaleString()} token/月</div>
              </div>
              {p.plan === subscription?.plan && (
                <Badge variant="success" leftIcon={<Check className="h-2.5 w-2.5" />}>
                  当前方案
                </Badge>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function UsageBar({ label, used, total }: { label: string; used: number; total: number }) {
  const pct = total > 0 ? (used / total) * 100 : 0
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-ink-2">{label}</span>
        <span className="text-ink-3 tabular-nums">
          {used.toLocaleString()} <span className="text-ink-muted">/ {total.toLocaleString()}</span>
        </span>
      </div>
      <Progress value={pct} size="sm" variant={pct > 80 ? 'warning' : 'brand'} />
    </div>
  )
}

/**
 * REQ-061 (US8 / T057) — Personal AI points center: balance, ledger, budget.
 * No RMB price, purchase, recharge or payment controls.
 */
import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { Coins, Crown, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { AIPointLedger } from '@/components/ai/AIPointLedger'
import {
  useAIPointAccount,
  useAIPointBudget,
  useExportAIPointLedger,
  useUpdateAIPointBudget,
} from '@/hooks/queries/useAIPoints'
import type { PointEventType } from '@/types/ai-metering'

const EVENT_FILTERS: { value: '' | PointEventType; label: string }[] = [
  { value: '', label: '全部类型' },
  { value: 'grant', label: '发放' },
  { value: 'expire', label: '失效' },
  { value: 'reserve', label: '预留' },
  { value: 'settle', label: '结算' },
  { value: 'release', label: '释放' },
  { value: 'refund', label: '退回' },
  { value: 'compensate', label: '补偿' },
  { value: 'reverse', label: '冲正' },
]

function newIdempotencyKey(prefix: string): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN')
}

export default function AIPoints() {
  const [eventType, setEventType] = useState<'' | PointEventType>('')
  const [dailyLimitDraft, setDailyLimitDraft] = useState<string>('')
  const budgetInputId = useId()

  const accountQuery = useAIPointAccount()
  const budgetQuery = useAIPointBudget()
  const exportMutation = useExportAIPointLedger()
  const updateBudget = useUpdateAIPointBudget()

  const account = accountQuery.data
  const budget = budgetQuery.data

  useEffect(() => {
    if (budget && dailyLimitDraft === '') {
      setDailyLimitDraft(String(budget.daily_limit))
    }
  }, [budget, dailyLimitDraft])

  function handleExport() {
    const to = new Date()
    const from = new Date(to)
    from.setMonth(from.getMonth() - 3)
    exportMutation.mutate({
      body: { from: from.toISOString(), to: to.toISOString() },
      idempotencyKey: newIdempotencyKey('export'),
    })
  }

  function handleSaveBudget() {
    if (!budget) return
    const parsed = Number.parseInt(dailyLimitDraft || String(budget.daily_limit), 10)
    if (!Number.isFinite(parsed) || parsed < 0) return
    updateBudget.mutate({
      body: { daily_limit: parsed, expected_version: budget.version },
      idempotencyKey: newIdempotencyKey('budget'),
    })
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 md:p-6" data-testid="ai-points-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink-1 flex items-center gap-2">
            <Coins className="h-5 w-5 text-brand-500" />
            体验点数
          </h1>
          <p className="mt-1 text-sm text-ink-3">
            查看余额、预留、明细与个人日限额。内测期间不涉及人民币购买或充值。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/ai-tasks"
            className="text-sm text-brand-600 dark:text-brand-300 hover:underline"
          >
            AI 任务中心
          </Link>
          <Button
            variant="secondary"
            size="sm"
            leftIcon={
              <RefreshCw
                className={`h-3.5 w-3.5 ${accountQuery.isFetching ? 'animate-spin' : ''}`}
              />
            }
            onClick={() => {
              void accountQuery.refetch()
              void budgetQuery.refetch()
            }}
            disabled={accountQuery.isFetching}
          >
            刷新
          </Button>
        </div>
      </div>

      {accountQuery.isLoading ? (
        <Card className="flex items-center justify-center gap-2 p-8 text-sm text-ink-3">
          <Loader2 className="h-4 w-4 animate-spin" />
          加载账户…
        </Card>
      ) : accountQuery.isError || !account ? (
        <Card className="space-y-3 p-5" data-testid="ai-points-account-error">
          <p className="text-sm text-ink-2">点数账户加载失败，请稍后重试。</p>
          <Button variant="secondary" size="sm" onClick={() => accountQuery.refetch()}>
            重试
          </Button>
        </Card>
      ) : (
        <Card className="p-5 bg-gradient-to-br from-brand-50/40 to-surface dark:from-brand-500/5 dark:to-dark-surface border-brand-200/50 dark:border-brand-500/20">
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <Crown className="h-4 w-4 text-amber-500" />
            <span className="text-base font-semibold text-ink-1">{account.plan_label}</span>
            <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
              {account.experience_badge}
            </Badge>
            <span className="text-xs text-ink-3">
              业务日 {account.business_date} · {account.timezone}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="可用" value={account.available} />
            <Stat label="预留" value={account.reserved} />
            <Stat label="每日发放" value={account.daily_grant_amount} />
            <div>
              <div className="text-2xs text-ink-3">最近到期</div>
              <div className="text-sm font-medium text-ink-1 mt-0.5">
                {formatDateTime(account.next_expiry)}
              </div>
            </div>
          </div>
          {account.buckets.length > 0 && (
            <ul className="mt-4 space-y-1.5 border-t border-surface-border dark:border-dark-surface-border pt-3">
              {account.buckets.map((b) => (
                <li
                  key={b.bucket_id}
                  className="flex justify-between gap-2 text-xs text-ink-2"
                >
                  <span>
                    {b.bucket_type === 'compensation' ? '补偿' : '每日体验'}
                    {b.business_date ? ` · ${b.business_date}` : ''}
                  </span>
                  <span className="tabular-nums">
                    {b.available.toLocaleString()} 可用 / {b.reserved.toLocaleString()} 预留 · 到期{' '}
                    {formatDateTime(b.expires_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Card className="p-5">
        <CardHeader title="个人日限额" />
        {budgetQuery.isLoading ? (
          <p className="text-sm text-ink-3">加载预算…</p>
        ) : budgetQuery.isError || !budget ? (
          <div className="space-y-2">
            <p className="text-sm text-ink-2">预算加载失败。</p>
            <Button variant="secondary" size="sm" onClick={() => budgetQuery.refetch()}>
              重试
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <Stat label="日限额" value={budget.daily_limit} />
              <Stat label="今日已用" value={budget.consumed_today} />
              <Stat label="有效上限" value={budget.effective_limit} />
              <Stat label="风险上限" value={budget.risk_limit} />
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label htmlFor={budgetInputId} className="block text-2xs text-ink-3 mb-1">
                  调整日限额（点数，不含人民币）
                </label>
                <input
                  id={budgetInputId}
                  type="number"
                  min={0}
                  className="h-8 w-36 rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface px-2 text-sm tabular-nums"
                  value={dailyLimitDraft}
                  onChange={(e) => setDailyLimitDraft(e.target.value)}
                />
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveBudget}
                disabled={updateBudget.isPending}
              >
                {updateBudget.isPending ? '保存中…' : '保存限额'}
              </Button>
              {updateBudget.isError && (
                <span className="text-xs text-red-600 dark:text-red-400">
                  保存失败，可能版本冲突，请刷新后重试。
                </span>
              )}
              {updateBudget.isSuccess && (
                <span className="text-xs text-emerald-600 dark:text-emerald-400">已更新</span>
              )}
            </div>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <CardHeader title="点数明细" className="mb-0" />
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="h-8 rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface px-2 text-sm"
              value={eventType}
              onChange={(e) => setEventType(e.target.value as '' | PointEventType)}
              aria-label="按事件类型筛选"
            >
              {EVENT_FILTERS.map((opt) => (
                <option key={opt.value || 'all'} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleExport}
              disabled={exportMutation.isPending}
            >
              {exportMutation.isPending ? '导出中…' : '导出近 3 个月'}
            </Button>
          </div>
        </div>
        {exportMutation.isSuccess && (
          <p className="mb-2 text-xs text-ink-3">
            导出任务已受理（{exportMutation.data.status}），编号 {exportMutation.data.export_id}
          </p>
        )}
        {exportMutation.isError && (
          <p className="mb-2 text-xs text-red-600 dark:text-red-400">导出失败，请稍后重试。</p>
        )}
        <AIPointLedger
          filters={{
            event_type: eventType || undefined,
            limit: 20,
          }}
        />
      </Card>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xs text-ink-3">{label}</div>
      <div className="text-base font-semibold text-ink-1 mt-0.5 tabular-nums">
        {value.toLocaleString()}
      </div>
    </div>
  )
}

/**
 * REQ-061 T109 — Model policy admin UI (candidate/stable/traffic/evidence/rollback).
 */
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { aiModelPoliciesApi, type ModelPolicySummary } from '@/admin/api/ai-model-policies'
import { Button } from '@/components/ui/Button'

function newKey(prefix: string) {
  return `${prefix}-${globalThis.crypto?.randomUUID?.() ?? Date.now()}`
}

export function ModelPolicies() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<ModelPolicySummary | null>(null)
  const [traffic, setTraffic] = useState(1)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const listQuery = useQuery({
    queryKey: ['admin', 'model-policies'],
    queryFn: ({ signal }) => aiModelPoliciesApi.list(signal),
    staleTime: 15_000,
  })

  const items = listQuery.data?.items ?? []
  const candidates = useMemo(
    () => items.filter((i) => i.status === 'candidate' || i.status === 'gray' || i.status === 'draft'),
    [items],
  )
  const stables = useMemo(() => items.filter((i) => i.status === 'stable'), [items])

  const releaseMutation = useMutation({
    mutationFn: async (target: 'gray' | 'stable' | 'stopped') => {
      if (!selected) throw new Error('未选择策略')
      return aiModelPoliciesApi.release(
        selected.policy_version,
        {
          target_status: target,
          traffic_percent: traffic,
          eval_evidence_ref: selected.eval_evidence_ref || 'pending-eval',
          rollback_target: selected.rollback_target || selected.policy_version,
          reason: reason || 'admin release',
        },
        newKey('model-policy-release'),
      )
    },
    onSuccess: async () => {
      setError(null)
      await queryClient.invalidateQueries({ queryKey: ['admin', 'model-policies'] })
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : '发布失败')
    },
  })

  return (
    <div className="space-y-4 p-4" data-testid="model-policies-page">
      <header>
        <h1 className="text-xl font-semibold">模型策略</h1>
        <p className="mt-1 text-sm text-ink-3">
          管理候选/稳定路由、流量与回滚目标。用户侧只见 standard/quality，不暴露供应商名。
        </p>
      </header>

      {listQuery.isError && (
        <div role="alert" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">
          策略列表不可用
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded border border-surface-border p-3" data-testid="model-policies-list">
          <h2 className="mb-2 text-sm font-medium">全部版本</h2>
          <ul className="space-y-2 text-sm">
            {items.map((item) => (
              <li key={item.policy_version}>
                <button
                  type="button"
                  className="w-full rounded border border-line-2 px-3 py-2 text-left hover:border-brand-500"
                  data-testid={`model-policy-row-${item.policy_version}`}
                  onClick={() => setSelected(item)}
                >
                  <div className="font-medium">{item.policy_version}</div>
                  <div className="text-xs text-ink-3">
                    {item.capability} · {item.service_tier} · {item.status}
                    {typeof item.traffic_percent === 'number' ? ` · 流量 ${item.traffic_percent}%` : ''}
                  </div>
                </button>
              </li>
            ))}
            {items.length === 0 && !listQuery.isLoading && (
              <li className="text-ink-3">暂无策略版本</li>
            )}
          </ul>
        </section>

        <section className="space-y-3 rounded border border-surface-border p-3" data-testid="model-policy-detail">
          <h2 className="text-sm font-medium">详情 / 发布</h2>
          {!selected ? (
            <p className="text-sm text-ink-3">选择左侧策略查看候选路由、证据与回滚目标。</p>
          ) : (
            <>
              <dl className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <dt className="text-ink-3">主路由</dt>
                  <dd data-testid="model-policy-primary-route">{selected.primary_route || '—'}</dd>
                </div>
                <div>
                  <dt className="text-ink-3">回滚目标</dt>
                  <dd data-testid="model-policy-rollback-target">{selected.rollback_target || '—'}</dd>
                </div>
                <div>
                  <dt className="text-ink-3">评测证据</dt>
                  <dd data-testid="model-policy-evidence">{selected.eval_evidence_ref || '—'}</dd>
                </div>
                <div>
                  <dt className="text-ink-3">成本上限</dt>
                  <dd>{selected.cost_ceiling_rmb ?? '—'}</dd>
                </div>
              </dl>
              {(selected.allowed_fallbacks?.length ?? 0) > 0 && (
                <div className="text-xs" data-testid="model-policy-fallbacks">
                  允许回退：{selected.allowed_fallbacks!.join(', ')}
                </div>
              )}
              <label className="block text-xs">
                灰度流量 %
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={traffic}
                  onChange={(e) => setTraffic(Number(e.target.value))}
                  className="mt-1 w-full rounded border px-2 py-1"
                  data-testid="model-policy-traffic-input"
                />
              </label>
              <label className="block text-xs">
                原因
                <input
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="mt-1 w-full rounded border px-2 py-1"
                  data-testid="model-policy-reason"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => releaseMutation.mutate('gray')} data-testid="model-policy-release-gray">
                  发布灰度
                </Button>
                <Button size="sm" onClick={() => releaseMutation.mutate('stable')} data-testid="model-policy-release-stable">
                  升为稳定
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => releaseMutation.mutate('stopped')}
                  data-testid="model-policy-stop"
                >
                  停止并回滚
                </Button>
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </>
          )}

          <div className="border-t pt-3 text-xs" data-testid="model-policy-candidates">
            <div className="font-medium">候选 {candidates.length}</div>
            <div className="mt-1 text-ink-3">稳定 {stables.length}</div>
          </div>
        </section>
      </div>
    </div>
  )
}

export default ModelPolicies

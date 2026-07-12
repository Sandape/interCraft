/**
 * AIReleaseGovernance — REQ-061 US11 / T150.
 *
 * Candidate vs stable comparison, offline gate evidence, cohort stage,
 * stop reason, rollback target, and dual-approval override audit.
 * Seed/demo data until T148 admin API lands.
 */
import { useState } from 'react'

type DemoBatch = {
  releaseBatchId: string
  capability: string
  candidate: string
  stable: string
  status: string
  stagePercent: number
  gateVerdict: string
  gateReasons: string[]
  stopReason: string | null
  rollbackTarget: string
  overrides: Array<{
    id: string
    pm: string
    tech: string
    reason: string
    createdAt: string
  }>
}

const DEMO: DemoBatch = {
  releaseBatchId: 'rel-demo-061',
  capability: 'interview',
  candidate: 'policy.interview.cand-v2',
  stable: 'policy.interview.stable-v1',
  status: 'gray',
  stagePercent: 5,
  gateVerdict: 'pass',
  gateReasons: [],
  stopReason: null,
  rollbackTarget: 'policy.interview.stable-v1',
  overrides: [
    {
      id: 'ovr-demo-1',
      pm: 'pm-alice',
      tech: 'tech-bob',
      reason: '低流量能力补充离线评测后晋级观察',
      createdAt: '2026-07-11T08:00:00Z',
    },
  ],
}

export function AIReleaseGovernance() {
  const [batch] = useState<DemoBatch>(DEMO)

  return (
    <div className="ac-page" data-testid="ai-release-governance">
      <div className="ac-page__header">
        <h1 className="ac-page__title">AI 发布与灰度治理</h1>
        <p style={{ color: 'var(--ac-ink-muted)', fontSize: 13, marginTop: 4 }}>
          比较候选与稳定策略，查看门禁证据、cohort 阶段、停止原因与双人批准 override。
        </p>
      </div>

      <section
        data-testid="release-candidate-stable"
        style={{ marginBottom: 24 }}
      >
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>候选 / 稳定对比</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--ac-ink-faint)' }}>候选策略</div>
            <div data-testid="release-candidate-version">{batch.candidate}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--ac-ink-faint)' }}>稳定策略</div>
            <div data-testid="release-stable-version">{batch.stable}</div>
          </div>
        </div>
        <div style={{ marginTop: 8, fontSize: 13 }}>
          能力：{batch.capability} · 批次：{batch.releaseBatchId} · 状态：
          {batch.status}
        </div>
      </section>

      <section data-testid="release-gate-evidence" style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>离线门禁证据</h2>
        <div data-testid="release-gate-verdict">结论：{batch.gateVerdict}</div>
        <ul>
          {(batch.gateReasons.length ? batch.gateReasons : ['无阻断原因']).map(
            (r) => (
              <li key={r}>{r}</li>
            ),
          )}
        </ul>
      </section>

      <section data-testid="release-cohort-status" style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>Cohort 阶段</h2>
        <div data-testid="release-cohort-percent">
          当前流量：{batch.stagePercent}%（1 → 5 → 20 → 50 → 100）
        </div>
      </section>

      <section data-testid="release-stop-reason" style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>停止原因</h2>
        <div>{batch.stopReason ?? '未触发自动停止'}</div>
      </section>

      <section data-testid="release-rollback-target" style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>回滚目标</h2>
        <div data-testid="release-rollback-version">{batch.rollbackTarget}</div>
      </section>

      <section data-testid="release-override-audit">
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>双人批准 Override 审计</h2>
        {batch.overrides.length === 0 ? (
          <div>暂无 override</div>
        ) : (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th align="left">ID</th>
                <th align="left">产品负责人</th>
                <th align="left">技术/质量负责人</th>
                <th align="left">理由</th>
                <th align="left">时间</th>
              </tr>
            </thead>
            <tbody>
              {batch.overrides.map((o) => (
                <tr key={o.id} data-testid={`release-override-row-${o.id}`}>
                  <td>{o.id}</td>
                  <td>{o.pm}</td>
                  <td>{o.tech}</td>
                  <td>{o.reason}</td>
                  <td>{o.createdAt}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

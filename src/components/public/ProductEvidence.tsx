import { ArrowUpRight, CheckCircle2, CircleAlert, MessageSquareText } from 'lucide-react'
import { publicDemoData } from '@/data/publicDemoData'

export function TargetedResumeEvidence() {
  const { derivedResume } = publicDemoData
  return (
    <div className="evidence-panel overflow-hidden rounded-lg border border-surface-border bg-surface shadow-notion-md">
      <div className="grid border-b border-surface-border md:grid-cols-[1fr_0.95fr]">
        <div className="border-b border-surface-border p-5 md:border-b-0 md:border-r sm:p-6">
          <div className="flex items-center justify-between">
            <span className="text-2xs font-medium uppercase tracking-[0.14em] text-ink-3">岗位定制简历</span>
            <span className="tag-success">Demo 结果</span>
          </div>
          <h3 className="mt-4 text-lg font-semibold tracking-tight text-ink-1">{derivedResume.title}</h3>
          <div className="mt-5 grid grid-cols-[auto_1fr] items-center gap-4">
            <div className="flex h-20 w-20 items-center justify-center rounded-full border-[6px] border-brand-100 bg-surface text-2xl font-semibold tabular-nums text-ink-1">
              {derivedResume.matchScore}
            </div>
            <div>
              <div className="text-sm font-medium text-ink-1">匹配分析</div>
              <p className="mt-1 text-xs leading-relaxed text-ink-3">
                已覆盖岗位关键能力，仍需补足商业化与复杂决策证据。
              </p>
            </div>
          </div>
        </div>
        <div className="grid divide-y divide-surface-border">
          <EvidenceList
            title="已有优势"
            icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />}
            items={derivedResume.strengths}
          />
          <EvidenceList
            title="能力差距"
            icon={<CircleAlert className="h-4 w-4 text-amber-600" />}
            items={derivedResume.gaps}
          />
        </div>
      </div>
      <div className="p-5 sm:p-6">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-ink-1">优化建议</div>
            <p className="mt-0.5 text-xs text-ink-3">建议只改证据表达，不虚构经历</p>
          </div>
          <ArrowUpRight className="h-4 w-4 text-ink-muted" />
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {derivedResume.suggestions.map((suggestion, index) => (
            <div key={suggestion} className="flex gap-2 rounded-md bg-surface-subtle p-3 text-xs leading-relaxed text-ink-2">
              <span className="font-mono text-2xs text-ink-muted">0{index + 1}</span>
              {suggestion}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function EvidenceList({ title, icon, items }: { title: string; icon: React.ReactNode; items: readonly string[] }) {
  return (
    <div className="p-5 sm:p-6">
      <div className="flex items-center gap-2 text-xs font-semibold text-ink-1">
        {icon} {title}
      </div>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li key={item} className="text-xs leading-relaxed text-ink-2">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function RetentionEvidence() {
  const { counts, abilities } = publicDemoData
  return (
    <div className="retention-evidence grid overflow-hidden rounded-lg border border-surface-border bg-surface lg:grid-cols-[1.1fr_0.9fr]">
      <div className="border-b border-surface-border p-5 sm:p-7 lg:border-b-0 lg:border-r">
        <div className="flex items-center gap-2 text-2xs font-medium uppercase tracking-[0.14em] text-ink-3">
          <MessageSquareText className="h-4 w-4" /> Interview report
        </div>
        <div className="mt-5 grid grid-cols-[auto_1fr] items-center gap-5">
          <div className="text-center">
            <div className="text-4xl font-semibold tabular-nums tracking-tight text-ink-1">7.6</div>
            <div className="mt-1 text-2xs text-ink-3">综合表现 / 10</div>
          </div>
          <div className="border-l border-surface-border pl-5">
            <div className="text-sm font-semibold text-ink-1">模拟面试</div>
            <p className="mt-1 text-xs leading-relaxed text-ink-3">
              围绕目标岗位继续追问；报告中的薄弱问题会进入错题本，成为下一轮训练素材。
            </p>
          </div>
        </div>
        <div className="mt-6 grid grid-cols-3 divide-x divide-surface-border border-y border-surface-border py-3 text-center">
          <Metric value={counts.interviews} label="完成面试" />
          <Metric value={counts.mistakes} label="错题沉淀" />
          <Metric value={counts.dimensions} label="能力维度" />
        </div>
      </div>
      <div className="p-5 sm:p-7">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-sm font-semibold text-ink-1">能力画像</div>
            <p className="mt-1 text-xs text-ink-3">从单次表现，回到长期能力建设</p>
          </div>
          <span className="text-2xs text-ink-muted">示例数据</span>
        </div>
        <div className="mt-5 space-y-3">
          {abilities.slice(0, 4).map((ability) => (
            <div key={ability.label} className="grid grid-cols-[72px_1fr_28px] items-center gap-3">
              <div className="text-xs text-ink-2">{ability.label}</div>
              <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted">
                <div className="h-full rounded-full bg-brand-900" style={{ width: `${ability.score * 10}%` }} />
              </div>
              <div className="text-right text-2xs tabular-nums text-ink-3">{ability.score}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="text-lg font-semibold tabular-nums text-ink-1">{value}</div>
      <div className="mt-0.5 text-2xs text-ink-3">{label}</div>
    </div>
  )
}

import { ArrowRight, Check, MessageSquareText } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { OnboardingState } from './onboarding-state'

export function OnboardingSuccess({ state }: { state: OnboardingState }) {
  const analysis = state.analysis
  if (!analysis) return null
  return (
    <div className="onboarding-success">
      <div className="flex items-center gap-2 text-2xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
        <Check className="h-4 w-4" /> Activated · Demo result
      </div>
      <h2 className="mt-4 text-3xl font-semibold tracking-[-0.025em] text-ink-1">第一份岗位定制简历已就绪</h2>
      <p className="mt-3 text-sm leading-7 text-ink-3">以下为 P0 界面预览数据，未调用真实 AI。你可以从这里继续体验完整工作流。</p>
      <div className="mt-7 grid gap-4 lg:grid-cols-[0.55fr_1.45fr]">
        <div className="flex min-h-52 flex-col justify-between bg-brand-900 p-6 text-white">
          <div className="text-2xs uppercase tracking-[0.14em] text-white/55">Match preview</div>
          <div><div className="text-6xl font-semibold tabular-nums">{analysis.matchScore}</div><div className="mt-2 text-xs text-white/60">匹配度 / 100</div></div>
        </div>
        <div className="grid gap-px overflow-hidden border border-surface-border bg-surface-border sm:grid-cols-2">
          <ResultList title="已有优势" items={analysis.strengths} />
          <ResultList title="能力差距" items={analysis.gaps} />
          <ResultList title="优化建议" items={analysis.suggestions} wide />
        </div>
      </div>
      <div className="mt-6 flex flex-col gap-3 border-t border-surface-border pt-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3"><MessageSquareText className="mt-0.5 h-4 w-4 text-brand-600" /><div><div className="text-sm font-semibold text-ink-1">推荐下一步：针对这个岗位模拟面试</div><p className="mt-1 text-xs text-ink-3">带着岗位和简历上下文继续练习。</p></div></div>
        <div className="flex gap-2"><Link to="/dashboard" className="btn-secondary btn-lg min-h-11">进入工作台</Link><Link to="/interview/mode?source=onboarding" className="btn-primary btn-lg min-h-11">准备模拟面试 <ArrowRight className="h-4 w-4" /></Link></div>
      </div>
    </div>
  )
}

function ResultList({ title, items, wide }: { title: string; items: string[]; wide?: boolean }) {
  return <section className={`bg-surface p-5 ${wide ? 'sm:col-span-2' : ''}`}><h3 className="text-xs font-semibold text-ink-1">{title}</h3><ul className="mt-3 space-y-2">{items.map((item) => <li key={item} className="flex gap-2 text-xs leading-6 text-ink-2"><span className="mt-2 h-1 w-1 flex-none rounded-full bg-brand-900" />{item}</li>)}</ul></section>
}

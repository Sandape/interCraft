import { FileStack, Lightbulb, LockKeyhole, MessageSquareText } from 'lucide-react'
import { WorkspacePreview } from './WorkspacePreview'
import { publicDemoData } from '@/data/publicDemoData'
import type { DemoView } from './DemoWorkspaceShell'

export function DemoWorkspaceView({ view }: { view: DemoView }) {
  if (view === 'resumes') return <ResumeView />
  if (view === 'jobs') return <JobsView />
  if (view === 'interviews') return <InterviewView />
  if (view === 'mistakes') return <MistakeView />
  if (view === 'abilities') return <AbilityView />
  return <OverviewView />
}

function OverviewView() {
  const { counts } = publicDemoData
  return (
    <div data-testid="demo-overview">
      <ViewHeading title="求职准备概览" body="一条岗位上下文贯穿简历、面试、复盘和能力沉淀。" />
      <div className="mt-5 grid grid-cols-2 border border-surface-border bg-surface sm:grid-cols-3 lg:grid-cols-6">
        <Metric value={counts.resumes} label="简历" />
        <Metric value={counts.jobs} label="目标岗位" />
        <Metric value={counts.interviews} label="完成面试" />
        <Metric value={counts.mistakes} label="错题" />
        <Metric value={counts.dimensions} label="能力维度" />
        <Metric value="82%" label="当前匹配" />
      </div>
      <div className="mt-5">
        <WorkspacePreview compact />
      </div>
    </div>
  )
}

function ResumeView() {
  return (
    <div>
      <ViewHeading title="简历中心" body="一份根简历，派生出面向具体岗位的版本。" />
      <div className="mt-6 grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <section className="border border-surface-border bg-surface p-5">
          <div className="text-2xs font-medium uppercase tracking-[0.14em] text-ink-3">Root resume</div>
          <h3 className="mt-3 text-base font-semibold text-ink-1">根简历 · 职业素材库</h3>
          <p className="mt-2 text-xs leading-6 text-ink-3">汇总示例候选人的经验、项目与可验证结果，不受单一岗位限制。</p>
          <div className="mt-5 flex flex-wrap gap-1.5">
            {publicDemoData.rootResume.signals.map((signal) => <span key={signal} className="tag-default">{signal}</span>)}
          </div>
        </section>
        <section className="border border-surface-border bg-surface">
          <div className="border-b border-surface-border px-5 py-4 text-sm font-semibold text-ink-1">派生简历</div>
          {[
            ['星河科技 · 高级产品经理', '匹配 82 · 3 条优化建议'],
            ['远山零售 · 增长产品经理', '匹配 76 · 4 条优化建议'],
          ].map(([title, meta]) => (
            <div key={title} className="flex items-center gap-3 border-b border-surface-border px-5 py-4 last:border-0">
              <FileStack className="h-4 w-4 flex-none text-ink-3" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-ink-1">{title}</div>
                <div className="mt-0.5 text-2xs text-ink-3">{meta}</div>
              </div>
              <LockKeyhole className="h-3.5 w-3.5 text-ink-muted" aria-label="只读" />
            </div>
          ))}
        </section>
      </div>
    </div>
  )
}

function JobsView() {
  const jobs = [
    ['星河科技', '高级产品经理', '面试中'],
    ['远山零售', '增长产品经理', '已投递'],
    ['云舟出行', '策略产品经理', '笔试中'],
    ['青石教育', '用户产品经理', '收藏'],
  ]
  return (
    <div>
      <ViewHeading title="目标岗位" body="岗位信息与简历版本、模拟面试保持关联。" />
      <div className="mt-6 overflow-hidden border border-surface-border bg-surface">
        <div className="hidden grid-cols-[1fr_1.4fr_0.7fr] border-b border-surface-border bg-surface-subtle px-5 py-3 text-2xs text-ink-3 sm:grid">
          <span>公司</span><span>岗位</span><span>状态</span>
        </div>
        {jobs.map(([company, role, status]) => (
          <div key={company} className="grid gap-2 border-b border-surface-border px-5 py-4 last:border-0 sm:grid-cols-[1fr_1.4fr_0.7fr] sm:items-center">
            <span className="text-sm font-medium text-ink-1">{company}</span>
            <span className="text-xs text-ink-2">{role}</span>
            <span className="tag-outline w-fit border border-surface-border px-2">{status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function InterviewView() {
  return (
    <div>
      <ViewHeading title="模拟面试报告" body="基于目标岗位和岗位定制简历组织问题与复盘。" />
      <div className="mt-6 grid gap-4 lg:grid-cols-[0.7fr_1.3fr]">
        <section className="flex min-h-56 flex-col justify-between bg-brand-900 p-6 text-white">
          <MessageSquareText className="h-5 w-5 text-white/65" />
          <div>
            <div className="text-5xl font-semibold tabular-nums">7.6</div>
            <div className="mt-2 text-xs text-white/60">高级产品经理 · 完整面试</div>
          </div>
        </section>
        <section className="border border-surface-border bg-surface p-5 sm:p-6">
          <div className="text-sm font-semibold text-ink-1">五维表现</div>
          <div className="mt-5 space-y-4">
            {[['产品判断', 81], ['数据分析', 74], ['协作推进', 83], ['商业理解', 62], ['表达沟通', 78]].map(([label, value]) => (
              <div key={label} className="grid grid-cols-[72px_1fr_30px] items-center gap-3 text-xs">
                <span className="text-ink-2">{label}</span>
                <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted"><div className="h-full rounded-full bg-brand-900" style={{ width: `${value}%` }} /></div>
                <span className="text-right tabular-nums text-ink-3">{value}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function MistakeView() {
  const questions = [
    '请讲一次你在数据不完整时做出产品取舍的经历。',
    '你如何判断一个 B 端功能值得继续投入？',
    '项目推进受阻时，你如何协调目标不一致的团队？',
  ]
  return (
    <div>
      <ViewHeading title="错题本" body="从面试中沉淀的薄弱问题，支持下一轮针对性训练。" />
      <div className="mt-6 border border-surface-border bg-surface">
        {questions.map((question, index) => (
          <div key={question} className="grid gap-3 border-b border-surface-border p-5 last:border-0 sm:grid-cols-[32px_1fr_auto] sm:items-center">
            <span className="font-mono text-2xs text-ink-muted">0{index + 1}</span>
            <div>
              <div className="text-sm text-ink-1">{question}</div>
              <div className="mt-1 text-2xs text-ink-3">来自模拟面试 · 待掌握</div>
            </div>
            <span className="tag-warning w-fit">高频</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function AbilityView() {
  return (
    <div>
      <ViewHeading title="能力画像" body="把重复出现的反馈整理为可观察的能力信号。" />
      <div className="mt-6 grid gap-px overflow-hidden border border-surface-border bg-surface-border sm:grid-cols-2">
        {publicDemoData.abilities.map((ability) => (
          <div key={ability.label} className="bg-surface p-5">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-ink-1">{ability.label}</span>
              <span className="text-sm tabular-nums text-ink-2">{ability.score} / 10</span>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-muted"><div className="h-full rounded-full bg-brand-900" style={{ width: `${ability.score * 10}%` }} /></div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ViewHeading({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-2xs font-medium uppercase tracking-[0.14em] text-ink-3">Sample candidate</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-ink-1">{title}</h2>
        <p className="mt-1 text-sm text-ink-3">{body}</p>
      </div>
      <div className="inline-flex items-center gap-2 text-xs text-ink-3"><Lightbulb className="h-3.5 w-3.5" /> 当前内容仅供产品演示</div>
    </div>
  )
}

function Metric({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="border-b border-r border-surface-border p-4 last:border-r-0 sm:p-5">
      <div className="text-xl font-semibold tabular-nums text-ink-1">{value}</div>
      <div className="mt-1 text-2xs text-ink-3">{label}</div>
    </div>
  )
}

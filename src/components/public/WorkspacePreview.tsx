import { ArrowRight, BriefcaseBusiness, Check, FileText, Target } from 'lucide-react'
import { publicDemoData } from '@/data/publicDemoData'
import { cn } from '@/lib/utils'

export function WorkspacePreview({ compact = false }: { compact?: boolean }) {
  const { rootResume, job, derivedResume } = publicDemoData

  return (
    <div
      className={cn(
        'workspace-preview overflow-hidden rounded-lg border border-surface-border bg-surface shadow-notion-lg',
        compact && 'workspace-preview-compact',
      )}
      aria-label="示例候选人的岗位定制简历工作台预览"
    >
      <div className="flex h-10 items-center justify-between border-b border-surface-border px-3 sm:px-4">
        <div className="flex items-center gap-1.5" aria-hidden="true">
          <span className="h-1.5 w-1.5 rounded-full bg-ink-muted/50" />
          <span className="h-1.5 w-1.5 rounded-full bg-ink-muted/30" />
          <span className="h-1.5 w-1.5 rounded-full bg-ink-muted/20" />
        </div>
        <div className="text-2xs font-medium text-ink-3">示例候选人 · 岗位准备工作台</div>
        <span className="tag-outline tag h-5 border border-surface-border bg-surface text-ink-2">示例数据</span>
      </div>

      <div className="preview-canvas bg-surface-subtle p-3 sm:p-5">
        <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4">
          <div>
            <p className="text-2xs font-medium uppercase tracking-[0.16em] text-ink-3">Activation preview</p>
            <h2 className="mt-1 text-base font-semibold tracking-tight text-ink-1 sm:text-lg">
              从职业素材，到岗位定制版本
            </h2>
          </div>
          <div className="hidden text-right sm:block">
            <div className="text-xl font-semibold tabular-nums text-ink-1">{derivedResume.matchScore}</div>
            <div className="text-2xs text-ink-3">岗位匹配度 / 100</div>
          </div>
        </div>

        <div className="preview-relationship grid gap-2 lg:grid-cols-[0.9fr_36px_0.9fr_36px_1.2fr] lg:items-stretch">
          <PreviewDocument
            eyebrow="ROOT RESUME"
            icon={<FileText className="h-3.5 w-3.5" />}
            title="根简历"
            subtitle={rootResume.title}
            lines={rootResume.signals}
          />
          <RelationshipArrow />
          <PreviewDocument
            eyebrow="TARGET JOB"
            icon={<BriefcaseBusiness className="h-3.5 w-3.5" />}
            title="目标岗位"
            subtitle={`${job.company} · ${job.title}`}
            lines={job.signals}
          />
          <RelationshipArrow />
          <div className="preview-derived min-w-0 rounded-md border border-brand-200 bg-surface p-3 shadow-notion-sm">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 text-2xs font-medium uppercase tracking-[0.13em] text-brand-600">
                <Target className="h-3.5 w-3.5" /> Derived
              </div>
              <span className="tag-success">已生成</span>
            </div>
            <h3 className="mt-2 text-sm font-semibold text-ink-1">派生简历</h3>
            <p className="mt-0.5 truncate text-xs text-ink-3">{derivedResume.title}</p>
            <div className="mt-3 grid gap-1.5">
              {derivedResume.strengths.map((item) => (
                <div key={item} className="flex items-start gap-1.5 text-2xs leading-relaxed text-ink-2">
                  <Check className="mt-0.5 h-3 w-3 flex-none text-emerald-600" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-surface-border pt-2">
              <div className="mb-1 flex items-center justify-between text-2xs text-ink-3">
                <span>匹配分析</span>
                <span className="font-medium tabular-nums text-ink-1">{derivedResume.matchScore}%</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted">
                <div className="h-full w-[82%] rounded-full bg-brand-900" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function PreviewDocument({
  eyebrow,
  icon,
  title,
  subtitle,
  lines,
}: {
  eyebrow: string
  icon: React.ReactNode
  title: string
  subtitle: string
  lines: readonly string[]
}) {
  return (
    <div className="min-w-0 rounded-md border border-surface-border bg-surface p-3">
      <div className="flex items-center gap-1.5 text-2xs font-medium uppercase tracking-[0.13em] text-ink-3">
        {icon} {eyebrow}
      </div>
      <h3 className="mt-2 text-sm font-semibold text-ink-1">{title}</h3>
      <p className="mt-0.5 truncate text-2xs text-ink-3">{subtitle}</p>
      <div className="mt-3 flex flex-wrap gap-1">
        {lines.map((line) => (
          <span key={line} className="rounded bg-surface-muted px-1.5 py-1 text-[10px] leading-none text-ink-2">
            {line}
          </span>
        ))}
      </div>
    </div>
  )
}

function RelationshipArrow() {
  return (
    <div className="relationship-arrow flex items-center justify-center text-ink-muted" aria-hidden="true">
      <ArrowRight className="h-4 w-4" />
    </div>
  )
}

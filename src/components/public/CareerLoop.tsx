import {
  BookOpenCheck,
  BriefcaseBusiness,
  FileStack,
  FileText,
  MessageSquareText,
  Radar,
} from 'lucide-react'
import { useInViewOnce } from '@/hooks/useInViewOnce'
import { cn } from '@/lib/utils'

const loopSteps = [
  { label: '根简历', detail: '沉淀可复用职业素材', icon: FileText },
  { label: '目标岗位', detail: '记录 JD 与求职进度', icon: BriefcaseBusiness },
  { label: '派生简历', detail: '围绕岗位重组证据', icon: FileStack },
  { label: '模拟面试', detail: '带着岗位上下文练习', icon: MessageSquareText },
  { label: '错题本', detail: '把薄弱问题变成训练', icon: BookOpenCheck },
  { label: '能力画像', detail: '看见积累与下一步', icon: Radar },
] as const

export function CareerLoop() {
  const { ref, inView } = useInViewOnce<HTMLOListElement>()

  return (
    <ol
      ref={ref}
      className={cn('career-loop relative grid gap-0 md:grid-cols-6', inView && 'is-visible')}
      aria-label="InterCraft 求职闭环"
    >
      <div className="loop-rail" aria-hidden="true">
        <span className="loop-progress" />
      </div>
      {loopSteps.map(({ label, detail, icon: Icon }, index) => (
        <li key={label} className="career-loop-step relative" style={{ '--loop-index': index } as React.CSSProperties}>
          <div className="loop-node relative z-10 flex h-10 w-10 items-center justify-center rounded-full border border-surface-border bg-surface text-ink-2">
            <Icon className="h-4 w-4" strokeWidth={1.7} />
          </div>
          <div className="loop-copy">
            <div className="text-xs font-semibold text-ink-1">
              <span className="mr-1.5 font-mono text-2xs font-normal text-ink-muted">0{index + 1}</span>
              {label}
            </div>
            <p className="mt-1 text-2xs leading-relaxed text-ink-3">{detail}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

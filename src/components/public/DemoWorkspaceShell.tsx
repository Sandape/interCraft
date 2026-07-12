import type { LucideIcon } from 'lucide-react'
import {
  BookOpenCheck,
  BriefcaseBusiness,
  FileText,
  LayoutDashboard,
  MessageSquareText,
  Radar,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type DemoView = 'overview' | 'resumes' | 'jobs' | 'interviews' | 'mistakes' | 'abilities'

const navItems: Array<{ id: DemoView; label: string; icon: LucideIcon }> = [
  { id: 'overview', label: '概览', icon: LayoutDashboard },
  { id: 'resumes', label: '简历', icon: FileText },
  { id: 'jobs', label: '岗位', icon: BriefcaseBusiness },
  { id: 'interviews', label: '模拟面试', icon: MessageSquareText },
  { id: 'mistakes', label: '错题本', icon: BookOpenCheck },
  { id: 'abilities', label: '能力画像', icon: Radar },
]

export function DemoWorkspaceNav({ active, onChange }: { active: DemoView; onChange: (view: DemoView) => void }) {
  return (
    <nav className="demo-workspace-nav" aria-label="示例工作台导航">
      {navItems.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          className={cn('demo-nav-item', active === id && 'is-active')}
          aria-current={active === id ? 'page' : undefined}
          onClick={() => onChange(id)}
        >
          <Icon className="h-4 w-4 flex-none" strokeWidth={1.7} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  )
}

import { useState } from 'react'
import {
  Plus,
  Search,
  Filter,
  MapPin,
  Briefcase,
  Calendar,
  ExternalLink,
  MoreHorizontal,
  Building2,
  ChevronRight,
  TrendingUp,
  CheckCircle2,
  Clock,
  XCircle,
  MessageSquare,
  FileText,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Tabs } from '@/components/ui/Tabs'
import { cn } from '@/lib/utils'

interface JobApplication {
  id: string
  company: string
  position: string
  city: string
  salary: string
  status: 'wishlist' | 'applied' | 'screening' | 'interview' | 'offer' | 'rejected'
  appliedDate: string
  nextStep?: string
  matchScore: number
  link: string
  notes: string
}

const jobs: JobApplication[] = [
  {
    id: 'j-1',
    company: '字节跳动',
    position: '高级前端工程师',
    city: '北京',
    salary: '40-65K · 16 薪',
    status: 'interview',
    appliedDate: '2026-06-01',
    nextStep: '二面 · 6月14日 14:00',
    matchScore: 87,
    link: 'https://jobs.bytedance.com/...',
    notes: 'HR 林女士非常 nice，已确认二面时间',
  },
  {
    id: 'j-2',
    company: '美团',
    position: '高级前端工程师',
    city: '北京',
    salary: '35-55K · 15 薪',
    status: 'offer',
    appliedDate: '2026-05-18',
    nextStep: 'Offer 审批中',
    matchScore: 92,
    link: 'https://zhaopin.meituan.com/...',
    notes: '面试 5 轮全部通过，等待正式 offer',
  },
  {
    id: 'j-3',
    company: '小红书',
    position: '资深前端工程师',
    city: '上海',
    city2: '北京',
    salary: '45-70K',
    status: 'screening',
    appliedDate: '2026-06-08',
    nextStep: '等待 HR 初筛',
    matchScore: 78,
    link: 'https://job.xiaohongshu.com/...',
    notes: 'HR 已读未回',
  } as any,
  {
    id: 'j-4',
    company: '腾讯',
    position: 'Web 前端开发',
    city: '深圳',
    salary: '30-50K · 14 薪',
    status: 'rejected',
    appliedDate: '2026-05-25',
    matchScore: 85,
    link: 'https://careers.tencent.com/...',
    notes: '一面挂，原因是项目经验与岗位匹配度不高',
  },
  {
    id: 'j-5',
    company: '蚂蚁集团',
    position: '前端架构师',
    city: '杭州',
    salary: '60-90K',
    status: 'applied',
    appliedDate: '2026-06-10',
    matchScore: 89,
    link: 'https://talent.antgroup.com/...',
    notes: '内推投递，等待反馈',
  },
  {
    id: 'j-6',
    company: 'Shopee',
    position: 'Senior Frontend',
    city: '新加坡',
    salary: 'SGD 12-18K',
    status: 'wishlist',
    appliedDate: '',
    matchScore: 76,
    link: 'https://shopee.com/careers/...',
    notes: '海外机会，需要英文面试准备',
  },
]

const statusMap: Record<JobApplication['status'], { label: string; tone: 'default' | 'brand' | 'warning' | 'success' | 'danger'; icon: any }> = {
  wishlist: { label: '关注中', tone: 'default', icon: Clock },
  applied: { label: '已投递', tone: 'brand', icon: FileText },
  screening: { label: '简历筛选', tone: 'warning', icon: Filter },
  interview: { label: '面试中', tone: 'brand', icon: MessageSquare },
  offer: { label: 'Offer 阶段', tone: 'success', icon: CheckCircle2 },
  rejected: { label: '已拒绝', tone: 'danger', icon: XCircle },
}

export default function Jobs() {
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')

  const counts = {
    all: jobs.length,
    active: jobs.filter((j) => ['applied', 'screening', 'interview'].includes(j.status)).length,
    offer: jobs.filter((j) => j.status === 'offer').length,
    rejected: jobs.filter((j) => j.status === 'rejected').length,
  }

  const filtered = jobs.filter((j) => {
    if (tab === 'active' && !['applied', 'screening', 'interview'].includes(j.status)) return false
    if (tab === 'offer' && j.status !== 'offer') return false
    if (tab === 'rejected' && j.status !== 'rejected') return false
    if (search && !j.company.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">求职追踪</h1>
          <p className="text-sm text-ink-3 mt-1">
            管理你所有的求职机会 · 联动简历分支与模拟面试
          </p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-3.5 w-3.5" />}>
          添加职位
        </Button>
      </div>

      {/* 看板统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <KanbanStat label="总申请" value={counts.all.toString()} icon={<Briefcase className="h-4 w-4" />} />
        <KanbanStat label="进行中" value={counts.active.toString()} icon={<TrendingUp className="h-4 w-4" />} tone="brand" />
        <KanbanStat label="Offer" value={counts.offer.toString()} icon={<CheckCircle2 className="h-4 w-4" />} tone="success" />
        <KanbanStat label="已拒绝" value={counts.rejected.toString()} icon={<XCircle className="h-4 w-4" />} tone="danger" />
      </div>

      <div className="flex items-center justify-between gap-3 mb-4">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { key: 'all', label: '全部', count: counts.all },
            { key: 'active', label: '进行中', count: counts.active },
            { key: 'offer', label: 'Offer', count: counts.offer },
            { key: 'rejected', label: '已拒绝', count: counts.rejected },
          ]}
        />
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索公司…"
            className="h-8 pl-8 pr-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 w-56"
          />
        </div>
      </div>

      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-2xs text-ink-3 uppercase tracking-wider border-b border-surface-border dark:border-dark-surface-border">
                <th className="px-4 py-2.5 font-medium">公司 / 岗位</th>
                <th className="px-4 py-2.5 font-medium">状态</th>
                <th className="px-4 py-2.5 font-medium">匹配度</th>
                <th className="px-4 py-2.5 font-medium">薪资</th>
                <th className="px-4 py-2.5 font-medium">下一步</th>
                <th className="px-4 py-2.5 font-medium w-10"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((j) => {
                const S = statusMap[j.status]
                return (
                  <tr
                    key={j.id}
                    className="border-b border-surface-border dark:border-dark-surface-border last:border-0 hover:bg-surface-muted/40 dark:hover:bg-dark-surface-muted/30 transition-colors group"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-md bg-surface-muted dark:bg-dark-surface-muted flex items-center justify-center text-ink-2 dark:text-dark-ink-secondary flex-shrink-0">
                          <Building2 className="h-3.5 w-3.5" />
                        </div>
                        <div className="min-w-0">
                          <div className="font-medium text-ink-1">{j.company}</div>
                          <div className="text-2xs text-ink-3 mt-0.5">{j.position}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={S.tone} leftIcon={<S.icon className="h-2.5 w-2.5" />}>
                        {S.label}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'font-semibold tabular-nums',
                            j.matchScore >= 90
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : j.matchScore >= 80
                                ? 'text-brand-600 dark:text-brand-300'
                                : 'text-amber-600 dark:text-amber-400',
                          )}
                        >
                          {j.matchScore}
                        </span>
                        <div className="w-16 h-1 rounded-full bg-surface-muted dark:bg-dark-surface-muted overflow-hidden">
                          <div
                            className={cn(
                              'h-full rounded-full',
                              j.matchScore >= 90
                                ? 'bg-emerald-500'
                                : j.matchScore >= 80
                                  ? 'bg-brand-500'
                                  : 'bg-amber-500',
                            )}
                            style={{ width: `${j.matchScore}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-ink-1 text-xs">{j.salary}</div>
                      <div className="text-2xs text-ink-3 flex items-center gap-0.5 mt-0.5">
                        <MapPin className="h-2.5 w-2.5" />
                        {j.city}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {j.nextStep ? (
                        <div className="text-xs text-ink-2">{j.nextStep}</div>
                      ) : j.appliedDate ? (
                        <div className="text-2xs text-ink-3">{j.appliedDate} 投递</div>
                      ) : (
                        <span className="text-2xs text-ink-muted">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button className="p-1 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 opacity-0 group-hover:opacity-100 transition-all">
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function KanbanStat({
  label,
  value,
  icon,
  tone = 'default',
}: {
  label: string
  value: string
  icon: React.ReactNode
  tone?: 'default' | 'brand' | 'success' | 'danger'
}) {
  const toneClass = {
    default: 'bg-surface-muted dark:bg-dark-surface-muted text-ink-2 dark:text-dark-ink-secondary',
    brand: 'bg-brand-50 dark:bg-brand-500/10 text-brand-600 dark:text-brand-300',
    success: 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    danger: 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400',
  }
  return (
    <Card className="p-4 flex items-center gap-3">
      <div className={cn('h-9 w-9 rounded-md flex items-center justify-center', toneClass[tone])}>
        {icon}
      </div>
      <div>
        <div className="text-2xl font-semibold text-ink-1 tabular-nums tracking-tight">{value}</div>
        <div className="text-2xs text-ink-3">{label}</div>
      </div>
    </Card>
  )
}

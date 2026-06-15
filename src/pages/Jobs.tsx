import { useState } from 'react'
import {
  Plus,
  Search,
  Briefcase,
  MoreHorizontal,
  Building2,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Trash2,
  Loader2,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Tabs } from '@/components/ui/Tabs'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { JobStatusBadge } from '@/components/jobs/StatusBadge'
import { useJobs, useJobStats } from '@/hooks/queries/useJobs'
import { OfflineBanner } from '@/components/lock/OfflineBanner'
import { useCreateJob, useUpdateJobStatus, useDeleteJob } from '@/hooks/mutations/useJobMutations'
import type { Job } from '@/repositories/JobRepository'

const STATUS_TABS = [
  { key: 'all', label: '全部' },
  { key: 'applied', label: '已投递' },
  { key: 'screening', label: '筛选' },
  { key: 'interview', label: '面试' },
  { key: 'offer', label: 'Offer' },
  { key: 'rejected', label: '已拒绝' },
]

const NEXT_STATUS: Record<string, string> = {
  applied: 'screening',
  screening: 'interview',
  interview: 'offer',
}

export default function Jobs() {
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const status = tab === 'all' ? undefined : tab
  const { data: jobsData, isLoading } = useJobs({ status })
  const { data: statsData } = useJobStats()
  const createJob = useCreateJob()
  const updateStatus = useUpdateJobStatus()
  const deleteJob = useDeleteJob()

  const jobs = jobsData?.data ?? []
  const stats = statsData?.counts ?? {}
  const total = statsData?.total ?? jobs.length

  const counts = {
    all: total,
    active: (stats.applied ?? 0) + (stats.screening ?? 0) + (stats.interview ?? 0),
    offer: stats.offer ?? 0,
    rejected: stats.rejected ?? 0,
    withdrawn: stats.withdrawn ?? 0,
  }

  const filtered = jobs.filter((j) => {
    if (search && !j.company.toLowerCase().includes(search.toLowerCase()) && !j.position.toLowerCase().includes(search.toLowerCase())) return false
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
        <Button variant="primary" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setShowCreate(true)}>
          添加职位
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <KanbanStat label="总申请" value={String(counts.all)} icon={<Briefcase className="h-4 w-4" />} />
        <KanbanStat label="进行中" value={String(counts.active)} icon={<TrendingUp className="h-4 w-4" />} tone="brand" />
        <KanbanStat label="Offer" value={String(counts.offer)} icon={<CheckCircle2 className="h-4 w-4" />} tone="success" />
        <KanbanStat label="已拒绝" value={String(counts.rejected + counts.withdrawn)} icon={<XCircle className="h-4 w-4" />} tone="danger" />
      </div>

      <div className="flex items-center justify-between gap-3 mb-4">
        <Tabs
          value={tab}
          onChange={setTab}
          items={STATUS_TABS.map((t) => ({
            key: t.key,
            label: t.label,
          }))}
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

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 text-ink-3 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <Card className="py-12 text-center">
          <Briefcase className="h-8 w-8 text-ink-muted mx-auto mb-3" />
          <div className="text-sm text-ink-2">暂无求职记录</div>
          <div className="text-xs text-ink-3 mt-1">点击「添加职位」开始追踪</div>
        </Card>
      ) : (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-2xs text-ink-3 uppercase tracking-wider border-b border-surface-border dark:border-dark-surface-border">
                  <th className="px-4 py-2.5 font-medium">公司 / 岗位</th>
                  <th className="px-4 py-2.5 font-medium">状态</th>
                  <th className="px-4 py-2.5 font-medium">投递时间</th>
                  <th className="px-4 py-2.5 font-medium">备注</th>
                  <th className="px-4 py-2.5 font-medium w-10"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((j) => (
                  <JobRow
                    key={j.id}
                    job={j}
                    onAdvance={() => {
                      const next = NEXT_STATUS[j.status]
                      if (next) updateStatus.mutate({ id: j.id, to: next })
                    }}
                    onReject={() => updateStatus.mutate({ id: j.id, to: 'rejected' })}
                    onDelete={() => deleteJob.mutate(j.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {showCreate && (
        <CreateJobModal
          onClose={() => setShowCreate(false)}
          onCreate={(input) => createJob.mutate(input, { onSuccess: () => setShowCreate(false) })}
          isPending={createJob.isPending}
        />
      )}
      <OfflineBanner />
    </div>
  )
}

function JobRow({ job, onAdvance, onReject, onDelete }: { job: Job; onAdvance: () => void; onReject: () => void; onDelete: () => void }) {
  const next = NEXT_STATUS[job.status]
  return (
    <tr className="border-b border-surface-border dark:border-dark-surface-border last:border-0 hover:bg-surface-muted/40 dark:hover:bg-dark-surface-muted/30 transition-colors group">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-md bg-surface-muted dark:bg-dark-surface-muted flex items-center justify-center text-ink-2 dark:text-dark-ink-secondary flex-shrink-0">
            <Building2 className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0">
            <div className="font-medium text-ink-1">{job.company}</div>
            <div className="text-2xs text-ink-3 mt-0.5">{job.position}</div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <JobStatusBadge status={job.status} />
      </td>
      <td className="px-4 py-3 text-xs text-ink-2">
        {job.created_at ? new Date(job.created_at).toLocaleDateString('zh-CN') : '—'}
      </td>
      <td className="px-4 py-3">
        <span className="text-xs text-ink-3 line-clamp-1 max-w-[200px]">{job.note || '—'}</span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
          {next && (
            <button onClick={onAdvance} className="p-1 rounded text-ink-3 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-500/10" title={`推进到 ${next}`}>
              <TrendingUp className="h-3.5 w-3.5" />
            </button>
          )}
          {job.status !== 'rejected' && (
            <button onClick={onReject} className="p-1 rounded text-ink-3 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10" title="标记为已拒绝">
              <XCircle className="h-3.5 w-3.5" />
            </button>
          )}
          <button onClick={onDelete} className="p-1 rounded text-ink-3 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10" title="删除">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </td>
    </tr>
  )
}

function CreateJobModal({
  onClose,
  onCreate,
  isPending,
}: {
  onClose: () => void
  onCreate: (input: { company: string; position: string; note?: string }) => void
  isPending: boolean
}) {
  const [company, setCompany] = useState('')
  const [position, setPosition] = useState('')
  const [note, setNote] = useState('')

  return (
    <Modal open title="添加职位" onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1">公司 *</label>
          <Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="如：字节跳动" />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1">岗位 *</label>
          <Input value={position} onChange={(e) => setPosition(e.target.value)} placeholder="如：高级前端工程师" />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1">备注</label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="投递渠道、薪资范围等"
            rows={3}
            className="w-full px-3 py-2 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30 resize-none"
          />
        </div>
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>取消</Button>
        <Button variant="primary" onClick={() => onCreate({ company: company.trim(), position: position.trim(), note: note.trim() || undefined })} loading={isPending} disabled={!company.trim() || !position.trim()}>
          添加
        </Button>
      </div>
    </Modal>
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
      <div className={`h-9 w-9 rounded-md flex items-center justify-center ${toneClass[tone]}`}>
        {icon}
      </div>
      <div>
        <div className="text-2xl font-semibold text-ink-1 tabular-nums tracking-tight">{value}</div>
        <div className="text-2xs text-ink-3">{label}</div>
      </div>
    </Card>
  )
}

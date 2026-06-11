import { Link } from 'react-router-dom'
import { useState } from 'react'
import {
  Plus,
  Search,
  Filter,
  Sparkles,
  MoreHorizontal,
  Pin,
  PinOff,
  Copy,
  Trash2,
  Briefcase,
  Clock,
  ChevronRight,
  FileText,
  GitBranch,
  ArrowUpRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Tabs } from '@/components/ui/Tabs'
import { Modal } from '@/components/ui/Modal'
import { Input, Textarea } from '@/components/ui/Input'
import { resumeBranches } from '@/data/mockData'
import { timeAgo } from '@/lib/utils'
import { cn } from '@/lib/utils'

const statusMap = {
  draft: { label: '草稿', tone: 'default' as const, icon: AlertCircle },
  optimizing: { label: 'AI 优化中', tone: 'warning' as const, icon: Loader2 },
  ready: { label: '就绪', tone: 'success' as const, icon: CheckCircle2 },
  submitted: { label: '已投递', tone: 'brand' as const, icon: ArrowUpRight },
}

export default function ResumeList() {
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')
  const [newOpen, setNewOpen] = useState(false)

  const filtered = resumeBranches.filter((b) => {
    if (tab === 'pinned' && !b.isPinned) return false
    if (tab === 'optimizing' && b.status !== 'optimizing') return false
    if (search && !b.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const counts = {
    all: resumeBranches.length,
    pinned: resumeBranches.filter((b) => b.isPinned).length,
    optimizing: resumeBranches.filter((b) => b.status === 'optimizing').length,
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      {/* 页头 */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">简历中心</h1>
          <p className="text-sm text-ink-3 mt-1">
            维护一份核心简历，AI 将自动为每个目标岗位生成针对性分支版本
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" leftIcon={<GitBranch className="h-3.5 w-3.5" />}>
            版本历史
          </Button>
          <Button variant="primary" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setNewOpen(true)}>
            新建分支
          </Button>
        </div>
      </div>

      {/* 核心简历 Hero Card */}
      <Card className="mb-6 p-5 bg-gradient-to-br from-brand-50/50 to-surface dark:from-brand-500/5 dark:to-dark-surface border-brand-200/60 dark:border-brand-500/20">
        <div className="flex items-start gap-4">
          <div className="h-10 w-10 rounded-md bg-gradient-to-br from-brand-900 to-brand-600 dark:from-brand-500 dark:to-brand-300 flex items-center justify-center flex-shrink-0 shadow-notion-sm">
            <Sparkles className="h-4 w-4 text-white" strokeWidth={2.5} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-base font-semibold text-ink-1">核心简历</h2>
              <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
                数据源
              </Badge>
            </div>
            <p className="text-sm text-ink-2 leading-relaxed">
              所有定制简历分支的唯一起点。当前包含 7 个模块 · 12 个历史版本 · 3 年经验沉淀。
              在此编辑一次，AI 会在所有相关分支中同步更新（除非你锁定某个特定版本）。
            </p>
            <div className="flex flex-wrap gap-2 mt-3">
              <Link to="/resume/core">
                <Button size="sm" variant="primary" leftIcon={<FileText className="h-3.5 w-3.5" />}>
                  编辑核心简历
                </Button>
              </Link>
              <Button size="sm" variant="secondary" leftIcon={<GitBranch className="h-3.5 w-3.5" />}>
                查看同步状态
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* 工具栏 */}
      <div className="flex items-center justify-between gap-3 mb-4">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { key: 'all', label: '全部', count: counts.all },
            { key: 'pinned', label: '已置顶', count: counts.pinned },
            { key: 'optimizing', label: '优化中', count: counts.optimizing },
          ]}
        />
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索公司或岗位…"
              className="h-8 pl-8 pr-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 w-56"
            />
          </div>
          <Button size="md" variant="ghost" leftIcon={<Filter className="h-3.5 w-3.5" />}>
            筛选
          </Button>
        </div>
      </div>

      {/* 简历分支网格 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((b) => {
          const Status = statusMap[b.status]
          return (
            <Link key={b.id} to={`/resume/${b.id}`} className="group">
              <Card hover padding="md" className="h-full">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <div
                      className={cn(
                        'h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0',
                        b.isMain
                          ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300'
                          : 'bg-surface-muted dark:bg-dark-surface-muted text-ink-2 dark:text-dark-ink-secondary',
                      )}
                    >
                      {b.isMain ? <Sparkles className="h-3.5 w-3.5" /> : <Briefcase className="h-3.5 w-3.5" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-ink-1 truncate group-hover:text-brand-600 dark:group-hover:text-brand-300 transition-colors">
                        {b.name}
                      </div>
                      <div className="text-2xs text-ink-3 mt-0.5 truncate">
                        {b.position}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                    }}
                    className="p-1 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors"
                    aria-label="更多操作"
                  >
                    <MoreHorizontal className="h-3.5 w-3.5" />
                  </button>
                </div>

                {/* 状态 + 匹配度 */}
                <div className="flex items-center gap-2 mb-3">
                  <Badge variant={Status.tone} leftIcon={<Status.icon className="h-2.5 w-2.5" />}>
                    {Status.label}
                  </Badge>
                  {b.isPinned && (
                    <Badge variant="default" leftIcon={<Pin className="h-2.5 w-2.5" />}>
                      已置顶
                    </Badge>
                  )}
                </div>

                {!b.isMain && (
                  <div className="mb-3">
                    <div className="flex items-center justify-between text-2xs mb-1">
                      <span className="text-ink-3">JD 匹配度</span>
                      <span
                        className={cn(
                          'font-semibold tabular-nums',
                          b.matchScore >= 90
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : b.matchScore >= 80
                              ? 'text-brand-600 dark:text-brand-300'
                              : 'text-amber-600 dark:text-amber-400',
                        )}
                      >
                        {b.matchScore}
                        <span className="text-ink-3 font-normal">/100</span>
                      </span>
                    </div>
                    <div className="h-1 rounded-full bg-surface-muted dark:bg-dark-surface-muted overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all duration-500',
                          b.matchScore >= 90
                            ? 'bg-emerald-500'
                            : b.matchScore >= 80
                              ? 'bg-brand-500'
                              : 'bg-amber-500',
                        )}
                        style={{ width: `${b.matchScore}%` }}
                      />
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between text-2xs text-ink-3 pt-3 border-t border-surface-border dark:border-dark-surface-border">
                  <span className="flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5" />
                    {timeAgo(b.lastEdited)}
                  </span>
                  <span className="flex items-center gap-1">
                    <GitBranch className="h-2.5 w-2.5" />
                    {b.versionCount} 个版本
                  </span>
                </div>
              </Card>
            </Link>
          )
        })}
      </div>

      {/* 新建分支弹窗 */}
      <Modal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        title="新建简历分支"
        description="基于核心简历创建一个针对特定岗位的定制版本"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setNewOpen(false)}>
              取消
            </Button>
            <Button variant="primary" leftIcon={<Sparkles className="h-3.5 w-3.5" />}>
              创建并开始 AI 优化
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">目标公司</label>
            <Input placeholder="例如：字节跳动" />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">目标岗位</label>
            <Input placeholder="例如：高级前端工程师" />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">
              招聘 JD <span className="text-ink-3 font-normal">（粘贴后 AI 将自动分析匹配度）</span>
            </label>
            <Textarea
              placeholder="将招聘 JD 粘贴到这里…"
              rows={6}
              defaultValue=""
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}

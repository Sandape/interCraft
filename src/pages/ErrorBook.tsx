import { useState } from 'react'
import {
  Plus,
  Search,
  BookOpen,
  Trash2,
  RotateCcw,
  ChevronRight,
  X,
  Zap,
} from 'lucide-react'
import ErrorCoachPanel from '@/components/error-book/ErrorCoachPanel'
import { Card, CardHeader } from '@/components/ui/Card'
import { OfflineBanner } from '@/components/lock/OfflineBanner'
import { outboxRepo } from '@/lib/outbox/OutboxRepository'
import { Button } from '@/components/ui/Button'
import { Tabs } from '@/components/ui/Tabs'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { StatusBadge } from '@/components/errors/StatusBadge'
import { FrequencyBadge } from '@/components/errors/FrequencyBadge'
import { useErrorQuestions, useErrorQuestion } from '@/hooks/queries/useErrorQuestions'
import {
  useCreateErrorQuestion,
  useUpdateErrorQuestion,
  useArchiveErrorQuestion,
  useResetErrorQuestion,
} from '@/hooks/mutations/useErrorQuestionMutations'
import type { ErrorQuestion } from '@/repositories/ErrorQuestionRepository'

const DIMENSIONS = [
  'tech_depth',
  'architecture',
  'engineering_practice',
  'communication',
  'algorithm',
  'business',
]

const STATUS_TABS = [
  { key: 'all', label: '全部' },
  { key: 'fresh', label: '未掌握' },
  { key: 'practicing', label: '练习中' },
  { key: 'mastered', label: '已掌握' },
]

const NEXT_STATUS: Record<string, string> = {
  fresh: 'practicing',
  practicing: 'mastered',
}

export default function ErrorBook() {
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [dimensionFilter, setDimensionFilter] = useState<string>('')
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const status = statusFilter === 'all' ? undefined : statusFilter
  const dim = dimensionFilter || undefined

  const { data, isLoading } = useErrorQuestions({ status, dimension: dim })
  const createMutation = useCreateErrorQuestion()
  const archiveMutation = useArchiveErrorQuestion()
  const resetMutation = useResetErrorQuestion()

  const filtered = (data?.data ?? []).filter((eq) => {
    if (search && !eq.question_text.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const selected = selectedId ? filtered.find((e) => e.id === selectedId) : null

  // Phase 5 M17: Error Coach
  const [coachOpen, setCoachOpen] = useState(false)
  const [coachQuestionId, setCoachQuestionId] = useState<string | null>(null)

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">错题本</h1>
          <p className="text-sm text-ink-3 mt-1">
            记录与复习面试中答错的问题，系统化提升薄弱环节
          </p>
        </div>
        <Button variant="primary" leftIcon={<Plus className="h-3.5 w-3.5" />} onClick={() => setShowCreate(true)}>
          添加错题
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧列表 */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <Tabs
              value={statusFilter}
              onChange={setStatusFilter}
              items={STATUS_TABS.map((t) => ({
                key: t.key,
                label: t.label,
              }))}
            />
            <div className="flex items-center gap-2">
              <select
                value={dimensionFilter}
                onChange={(e) => setDimensionFilter(e.target.value)}
                className="h-8 px-2 text-xs rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
              >
                <option value="">全部维度</option>
                {DIMENSIONS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索题目…"
                  className="h-8 pl-8 pr-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 w-48"
                />
              </div>
            </div>
          </div>

          {isLoading ? (
            <div className="text-sm text-ink-3 py-12 text-center">加载中…</div>
          ) : filtered.length === 0 ? (
            <Card className="py-12 text-center">
              <BookOpen className="h-8 w-8 text-ink-muted mx-auto mb-3" />
              <div className="text-sm text-ink-2">还没有错题记录</div>
              <div className="text-xs text-ink-3 mt-1">点击「添加错题」开始记录</div>
            </Card>
          ) : (
            <div className="space-y-2">
              {filtered.map((eq) => (
                <ErrorCard
                  key={eq.id}
                  item={eq}
                  isSelected={eq.id === selectedId}
                  onSelect={() => setSelectedId(eq.id === selectedId ? null : eq.id)}
                  onAdvance={() => {
                    const next = NEXT_STATUS[eq.status]
                    if (next) {
                      useUpdateErrorQuestion().mutate({ id: eq.id, patch: { status: next } })
                    }
                  }}
                  onArchive={() => archiveMutation.mutate(eq.id, {
                    onSuccess: () => { if (selectedId === eq.id) setSelectedId(null) },
                  })}
                  onReset={() => resetMutation.mutate(eq.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* 右侧详情 */}
        <div className="lg:col-span-1">
          {selected ? (
            <ErrorDetail
              item={selected}
              onClose={() => setSelectedId(null)}
              onStartCoach={(id) => { setCoachQuestionId(id); setCoachOpen(true) }}
            />
          ) : (
            <Card className="p-5 text-center text-sm text-ink-3">
              <BookOpen className="h-6 w-6 text-ink-muted mx-auto mb-2" />
              选择左侧错题查看详情
            </Card>
          )}
        </div>
      </div>

      {/* 创建弹窗 */}
      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreate={(input) => createMutation.mutate(input, {
            onSuccess: () => setShowCreate(false),
          })}
          isPending={createMutation.isPending}
          error={createMutation.error}
        />
      )}
      <OfflineBanner />

      {/* Phase 5 M17: Error Coach */}
      {coachQuestionId && (
        <ErrorCoachPanel
          errorQuestionId={coachQuestionId}
          questionText={selected?.question_text ?? ''}
          open={coachOpen}
          onClose={() => { setCoachOpen(false); setCoachQuestionId(null) }}
        />
      )}
    </div>
  )
}

function ErrorCard({
  item,
  isSelected,
  onSelect,
  onAdvance,
  onArchive,
  onReset,
}: {
  item: ErrorQuestion
  isSelected: boolean
  onSelect: () => void
  onAdvance: () => void
  onArchive: () => void
  onReset: () => void
}) {
  return (
    <Card
      hover
      padding="md"
      className={isSelected ? 'ring-2 ring-brand-500/30' : ''}
      onClick={onSelect}
      data-testid={`error-question-${item.id}`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <StatusBadge status={item.status} />
            <FrequencyBadge frequency={item.frequency} />
            <span className="text-2xs text-ink-3">{item.dimension}</span>
          </div>
          <p className="text-sm text-ink-1 font-medium leading-snug line-clamp-2">
            {item.question_text}
          </p>
        </div>
        <ChevronRight className="h-4 w-4 text-ink-3 flex-shrink-0 mt-1" />
      </div>
    </Card>
  )
}

function ErrorDetail({
  item,
  onClose,
  onStartCoach,
}: {
  item: ErrorQuestion
  onClose: () => void
  onStartCoach: (id: string) => void
}) {
  const updateMutation = useUpdateErrorQuestion()
  const archiveMutation = useArchiveErrorQuestion()
  const resetMutation = useResetErrorQuestion()

  const nextStatus = NEXT_STATUS[item.status]

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-ink-1">错题详情</h3>
        <button onClick={onClose} className="p-1 rounded text-ink-3 hover:text-ink-1">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <StatusBadge status={item.status} />
        <FrequencyBadge frequency={item.frequency} />
      </div>

      <div className="text-xs text-ink-3 mb-1">题目</div>
      <p className="text-sm text-ink-1 mb-4 leading-relaxed">{item.question_text}</p>

      {item.answer_text && (
        <>
          <div className="text-xs text-ink-3 mb-1">参考答案</div>
          <p className="text-sm text-ink-2 mb-4 leading-relaxed">{item.answer_text}</p>
        </>
      )}

      <div className="text-xs text-ink-3 mb-1">维度</div>
      <p className="text-sm text-ink-2 mb-4">{item.dimension}</p>

      <div className="text-xs text-ink-3 mb-1">得分</div>
      <p className="text-sm text-ink-2 mb-4">{item.score}</p>

      <div className="space-y-2 pt-4 border-t border-surface-border dark:border-dark-surface-border">
        {item.frequency > 0 && (
          <Button variant="primary" size="sm" className="w-full" leftIcon={<Zap className="h-3.5 w-3.5" />} onClick={() => onStartCoach(item.id)} data-testid="start-coach-button">
            开始强化
          </Button>
        )}
        {nextStatus && (
          <Button variant="primary" size="sm" className="w-full" onClick={() => updateMutation.mutate({ id: item.id, patch: { status: nextStatus } })}>
            推进到 {STATUS_TABS.find((t) => t.key === nextStatus)?.label ?? nextStatus}
          </Button>
        )}
        {item.status === 'mastered' && (
          <Button variant="secondary" size="sm" className="w-full" leftIcon={<RotateCcw className="h-3.5 w-3.5" />} onClick={() => resetMutation.mutate(item.id)}>
            重置为未掌握
          </Button>
        )}
        <Button variant="ghost" size="sm" className="w-full" leftIcon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => archiveMutation.mutate(item.id, { onSuccess: onClose })}>
          归档
        </Button>
      </div>
    </Card>
  )
}

function CreateModal({
  onClose,
  onCreate,
  isPending,
  error,
}: {
  onClose: () => void
  onCreate: (input: { question_text: string; dimension?: string; answer_text?: string }) => void
  isPending: boolean
  error: Error | null
}) {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [dimension, setDimension] = useState('')

  const handleSubmit = () => {
    if (!question.trim()) return
    onCreate({
      question_text: question.trim(),
      dimension: dimension || undefined,
      answer_text: answer.trim() || undefined,
    })
  }

  return (
    <Modal open title="添加错题" onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1">题目 *</label>
          <TextareaInput value={question} onChange={setQuestion} placeholder="输入面试中答错的题目…" rows={3} />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1">参考答案</label>
          <TextareaInput value={answer} onChange={setAnswer} placeholder="输入参考答案或提示…" rows={3} />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1">所属维度</label>
          <select
            value={dimension}
            onChange={(e) => setDimension(e.target.value)}
            className="w-full h-9 px-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          >
            <option value="">选择维度（可选）</option>
            {DIMENSIONS.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
        {error && (
          <div role="alert" className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-md px-3 py-2">
            {error.message}
          </div>
        )}
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>取消</Button>
        <Button variant="primary" onClick={handleSubmit} loading={isPending} disabled={!question.trim()}>
          添加
        </Button>
      </div>
    </Modal>
  )
}

function TextareaInput({ value, onChange, placeholder, rows = 3 }: { value: string; onChange: (v: string) => void; placeholder: string; rows?: number }) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full px-3 py-2 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30 resize-none"
    />
  )
}

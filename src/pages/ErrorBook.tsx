import { useEffect, useMemo, useState } from 'react'
import {
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Link2,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  X,
  Zap,
} from 'lucide-react'
import ErrorCoachPanel from '@/components/error-book/ErrorCoachPanel'
import { Card } from '@/components/ui/Card'
import { OfflineBanner } from '@/components/lock/OfflineBanner'
import { Button } from '@/components/ui/Button'
import { Tabs } from '@/components/ui/Tabs'
import { Modal } from '@/components/ui/Modal'
import { StatusBadge } from '@/components/errors/StatusBadge'
import { FrequencyBadge } from '@/components/errors/FrequencyBadge'
import { useErrorQuestions } from '@/hooks/queries/useErrorQuestions'
import {
  useArchiveErrorQuestion,
  useClearErrorQuestionSource,
  useCreateErrorQuestion,
  useRecallErrorQuestion,
  useResetErrorQuestion,
} from '@/hooks/mutations/useErrorQuestionMutations'
import type { ErrorQuestion } from '@/repositories/ErrorQuestionRepository'
import { cn } from '@/lib/utils'

const DIMENSIONS = [
  { value: 'tech_depth', label: '技术深度' },
  { value: 'architecture', label: '系统设计' },
  { value: 'engineering_practice', label: '工程实践' },
  { value: 'communication', label: '沟通表达' },
  { value: 'algorithm', label: '算法' },
  { value: 'business', label: '业务理解' },
]

const STATUS_TABS = [
  { key: 'all', label: '全部' },
  { key: 'fresh', label: '未掌握' },
  { key: 'practicing', label: '练习中' },
  { key: 'mastered', label: '已掌握' },
]

// 020 (FIX-008, D-009) — source filter (auto / manual / all).
const SOURCE_FILTER_TABS = [
  { key: 'all', label: '全部' },
  { key: 'auto', label: '来自面试' },
  { key: 'manual', label: '手动录入' },
]

function dimensionLabel(value: string | null) {
  return DIMENSIONS.find((d) => d.value === value)?.label ?? '未分类'
}

function SourceBadge({ item }: { item: ErrorQuestion }) {
  if (!item.source_question_id) return null
  return (
    <span
      data-testid="error-source-badge"
      className="inline-flex items-center gap-1 rounded-full bg-purple-50 dark:bg-purple-900/20 px-2 py-0.5 text-2xs font-medium text-purple-700 dark:text-purple-300"
    >
      <Link2 className="h-2.5 w-2.5" />
      来自面试
    </span>
  )
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败，请稍后重试'
}

function formatDate(value: string | null) {
  if (!value) return '尚未练习'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function ErrorBook() {
  const [statusFilter, setStatusFilter] = useState('all')
  const [dimensionFilter, setDimensionFilter] = useState('')
  // 020 (FIX-008, D-009) — source filter state
  const [sourceFilter, setSourceFilter] = useState<'all' | 'auto' | 'manual'>('all')
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [coachQuestionId, setCoachQuestionId] = useState<string | null>(null)
  const [hiddenIds, setHiddenIds] = useState<Set<string>>(() => new Set())

  const queryParams = {
    status: statusFilter === 'all' ? undefined : statusFilter,
    dimension: dimensionFilter || undefined,
    source: sourceFilter === 'all' ? undefined : sourceFilter,
    limit: 50,
  }

  const { data, error, isLoading } = useErrorQuestions(queryParams)
  const createMutation = useCreateErrorQuestion()
  const archiveMutation = useArchiveErrorQuestion()
  const recallMutation = useRecallErrorQuestion()
  const resetMutation = useResetErrorQuestion()
  const clearSourceMutation = useClearErrorQuestionSource()

  const items = useMemo(
    () => (data?.data ?? []).filter((item) => !hiddenIds.has(item.id)),
    [data?.data, hiddenIds],
  )
  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) return items
    return items.filter((eq) => {
      const haystack = [
        eq.question_text,
        eq.answer_text ?? '',
        eq.reference_answer_md ?? '',
        dimensionLabel(eq.dimension),
      ].join(' ').toLowerCase()
      return haystack.includes(keyword)
    })
  }, [items, search])

  const selected = selectedId ? items.find((eq) => eq.id === selectedId) ?? null : null

  useEffect(() => {
    if (!selectedId) return
    if (!items.some((eq) => eq.id === selectedId)) {
      setSelectedId(null)
    }
  }, [items, selectedId])

  const handleCreate = (input: { question_text: string; dimension?: string; answer_text?: string }) => {
    setFeedback(null)
    createMutation.mutate(input, {
      onSuccess: (created) => {
        setShowCreate(false)
        setSelectedId(created.id)
        setFeedback('错题已添加')
      },
    })
  }

  const handleRecall = (id: string) => {
    setFeedback(null)
    recallMutation.mutate(id, {
      onSuccess: () => setFeedback('已记录一次答对'),
      onError: (err) => setFeedback(errorMessage(err)),
    })
  }

  const handleReset = (id: string) => {
    setFeedback(null)
    resetMutation.mutate(id, {
      onSuccess: () => setFeedback('已重置为未掌握'),
      onError: (err) => setFeedback(errorMessage(err)),
    })
  }

  const handleClearSource = (id: string) => {
    setFeedback(null)
    clearSourceMutation.mutate(id, {
      onSuccess: () => setFeedback('已清除面试来源，变为手动错题'),
      onError: (err) => setFeedback(errorMessage(err)),
    })
  }

  const handleArchive = (id: string) => {
    setFeedback(null)
    setHiddenIds((current) => new Set(current).add(id))
    if (selectedId === id) setSelectedId(null)
    archiveMutation.mutate(id, {
      onSuccess: () => {
        setFeedback('错题已删除')
      },
      onError: (err) => {
        setHiddenIds((current) => {
          const next = new Set(current)
          next.delete(id)
          return next
        })
        setFeedback(errorMessage(err))
      },
    })
  }

  const listError = error ? errorMessage(error) : null
  const emptyCopy = search.trim() || statusFilter !== 'all' || dimensionFilter
    ? '没有匹配当前条件的错题'
    : '还没有错题记录'

  return (
    <div className="px-4 py-5 sm:px-6 lg:px-8 max-w-7xl mx-auto">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">错题本</h1>
          <p className="text-sm text-ink-3 mt-1">
            记录、复习并消灭面试中的薄弱问题。
          </p>
        </div>
        <Button
          variant="primary"
          leftIcon={<Plus className="h-3.5 w-3.5" />}
          onClick={() => {
            setFeedback(null)
            setShowCreate(true)
          }}
        >
          添加错题
        </Button>
      </div>

      {(feedback || listError) && (
        <div
          role="alert"
          className="mb-4 rounded-md border border-surface-border bg-surface-muted px-3 py-2 text-sm text-ink-2 dark:border-dark-surface-border dark:bg-dark-surface-muted"
        >
          {feedback ?? listError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <Tabs
              value={statusFilter}
              onChange={(value) => {
                setStatusFilter(value)
                setSelectedId(null)
              }}
              items={STATUS_TABS}
            />
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-[180px_minmax(180px,240px)]">
              <label className="sr-only" htmlFor="error-dimension-filter">能力维度</label>
              <select
                id="error-dimension-filter"
                value={dimensionFilter}
                onChange={(e) => {
                  setDimensionFilter(e.target.value)
                  setSelectedId(null)
                }}
                className="h-9 px-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30"
              >
                <option value="">全部维度</option>
                {DIMENSIONS.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索题目..."
                  className="h-9 w-full pl-8 pr-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                />
              </div>
            </div>
          </div>

          {/* 020 (FIX-008, D-009) — source filter segmented control */}
          <div data-testid="error-source-filter">
            <Tabs
              value={sourceFilter}
              onChange={(value) => {
                setSourceFilter(value as 'all' | 'auto' | 'manual')
                setSelectedId(null)
              }}
              items={SOURCE_FILTER_TABS}
              getTabId={(k) => `error-source-filter-${k}`}
            />
          </div>

          {isLoading ? (
            <Card className="py-12 text-center text-sm text-ink-3" aria-busy="true">
              加载中...
            </Card>
          ) : filtered.length === 0 ? (
            <Card className="py-12 text-center">
              <BookOpen className="h-8 w-8 text-ink-muted mx-auto mb-3" />
              <div className="text-sm text-ink-2">{emptyCopy}</div>
              <div className="text-xs text-ink-3 mt-1">
                {items.length === 0 ? '点击“添加错题”开始记录。' : '调整筛选或搜索关键词后再试。'}
              </div>
            </Card>
          ) : (
            <div className="space-y-2" role="list" aria-label="错题列表">
              {filtered.map((eq) => (
                <ErrorCard
                  key={eq.id}
                  item={eq}
                  isSelected={eq.id === selectedId}
                  onSelect={() => setSelectedId(eq.id === selectedId ? null : eq.id)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {selected ? (
            <ErrorDetail
              item={selected}
              isBusy={recallMutation.isPending || resetMutation.isPending || archiveMutation.isPending || clearSourceMutation.isPending}
              onClose={() => setSelectedId(null)}
              onRecall={handleRecall}
              onReset={handleReset}
              onArchive={handleArchive}
              onClearSource={handleClearSource}
              onStartCoach={(id) => setCoachQuestionId(id)}
            />
          ) : (
            <Card className="p-5 text-center text-sm text-ink-3">
              <BookOpen className="h-6 w-6 text-ink-muted mx-auto mb-2" />
              选择左侧错题查看详情
            </Card>
          )}
        </div>
      </div>

      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreate={handleCreate}
          isPending={createMutation.isPending}
          error={createMutation.error}
        />
      )}

      <OfflineBanner />

      {coachQuestionId && (
        <ErrorCoachPanel
          errorQuestionId={coachQuestionId}
          questionText={items.find((eq) => eq.id === coachQuestionId)?.question_text ?? ''}
          open={Boolean(coachQuestionId)}
          onClose={() => setCoachQuestionId(null)}
        />
      )}
    </div>
  )
}

function ErrorCard({
  item,
  isSelected,
  onSelect,
}: {
  item: ErrorQuestion
  isSelected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={cn(
        'card-hover w-full p-4 text-left transition-colors',
        isSelected && 'ring-2 ring-brand-500/30',
      )}
      onClick={onSelect}
      data-testid={`error-question-${item.id}`}
      aria-pressed={isSelected}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <StatusBadge status={item.status} />
            <FrequencyBadge frequency={item.frequency} />
            <span className="text-2xs text-ink-3">{dimensionLabel(item.dimension)}</span>
            <SourceBadge item={item} />
          </div>
          <p className="text-sm text-ink-1 font-medium leading-snug line-clamp-2">
            {item.question_text}
          </p>
          <p className="mt-2 text-xs text-ink-3">
            最近练习：{formatDate(item.last_practiced_at)}
          </p>
        </div>
        <ChevronRight className="h-4 w-4 text-ink-3 flex-shrink-0 mt-1" aria-hidden />
      </div>
    </button>
  )
}

function ErrorDetail({
  item,
  isBusy,
  onClose,
  onRecall,
  onReset,
  onArchive,
  onClearSource,
  onStartCoach,
}: {
  item: ErrorQuestion
  isBusy: boolean
  onClose: () => void
  onRecall: (id: string) => void
  onReset: (id: string) => void
  onArchive: (id: string) => void
  onClearSource: (id: string) => void
  onStartCoach: (id: string) => void
}) {
  return (
    <Card className="p-5" data-testid="error-detail">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-ink-1">错题详情</h2>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded text-ink-3 hover:text-ink-1"
          aria-label="关闭详情"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <StatusBadge status={item.status} />
        <FrequencyBadge frequency={item.frequency} />
      </div>

      <DetailField label="题目" value={item.question_text} />
      <DetailField label="参考答案" value={item.answer_text || item.reference_answer_md || '暂无参考答案'} />
      <DetailField label="能力维度" value={dimensionLabel(item.dimension)} />
      <DetailField label="得分" value={item.score == null ? '未评分' : `${item.score}/10`} />
      <DetailField label="最近练习" value={formatDate(item.last_practiced_at)} />

      {item.source_question_id && (
        <div className="mb-4 rounded-md bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Link2 className="h-3 w-3 text-purple-600 dark:text-purple-400" />
            <span className="text-xs font-medium text-purple-700 dark:text-purple-300">面试来源</span>
          </div>
          <p className="text-xs text-purple-600 dark:text-purple-400 mb-2">
            此错题自动来自面试评分。清除来源后可变为手动错题。
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-800/30"
            onClick={() => onClearSource(item.id)}
            loading={isBusy}
          >
            清除来源
          </Button>
        </div>
      )}

      <div className="space-y-2 pt-4 border-t border-surface-border dark:border-dark-surface-border">
        {item.frequency > 0 && (
          <Button
            variant="primary"
            size="sm"
            className="w-full"
            leftIcon={<CheckCircle2 className="h-3.5 w-3.5" />}
            onClick={() => onRecall(item.id)}
            loading={isBusy}
          >
            答对一次
          </Button>
        )}
        {item.frequency > 0 && (
          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            leftIcon={<Zap className="h-3.5 w-3.5" />}
            onClick={() => onStartCoach(item.id)}
            data-testid="start-coach-button"
          >
            开始强化
          </Button>
        )}
        {item.status === 'mastered' && (
          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
            onClick={() => onReset(item.id)}
            loading={isBusy}
          >
            重置为未掌握
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="w-full"
          leftIcon={<Trash2 className="h-3.5 w-3.5" />}
          onClick={() => onArchive(item.id)}
          disabled={isBusy}
        >
          删除
        </Button>
      </div>
    </Card>
  )
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-4">
      <div className="text-xs text-ink-3 mb-1">{label}</div>
      <p className="text-sm text-ink-2 leading-relaxed whitespace-pre-wrap">{value}</p>
    </div>
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

  const canSubmit = question.trim().length > 0

  const handleSubmit = () => {
    if (!canSubmit) return
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
          <label htmlFor="error-question-text" className="block text-xs font-medium text-ink-2 mb-1">
            题目
          </label>
          <TextareaInput
            id="error-question-text"
            value={question}
            onChange={setQuestion}
            placeholder="输入面试中答错的题目..."
            rows={3}
          />
        </div>
        <div>
          <label htmlFor="error-answer-text" className="block text-xs font-medium text-ink-2 mb-1">
            参考答案
          </label>
          <TextareaInput
            id="error-answer-text"
            value={answer}
            onChange={setAnswer}
            placeholder="输入参考答案或复习提示..."
            rows={3}
          />
        </div>
        <div>
          <label htmlFor="error-dimension" className="block text-xs font-medium text-ink-2 mb-1">
            能力维度
          </label>
          <select
            id="error-dimension"
            value={dimension}
            onChange={(e) => setDimension(e.target.value)}
            className="w-full h-9 px-3 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          >
            <option value="">选择维度（可选）</option>
            {DIMENSIONS.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </div>
        {error && (
          <div role="alert" className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-md px-3 py-2">
            {errorMessage(error)}
          </div>
        )}
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>取消</Button>
        <Button variant="primary" onClick={handleSubmit} loading={isPending} disabled={!canSubmit}>
          保存
        </Button>
      </div>
    </Modal>
  )
}

function TextareaInput({
  id,
  value,
  onChange,
  placeholder,
  rows = 3,
}: {
  id: string
  value: string
  onChange: (v: string) => void
  placeholder: string
  rows?: number
}) {
  return (
    <textarea
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full px-3 py-2 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border border-surface-border dark:border-dark-surface-border focus:outline-none focus:ring-2 focus:ring-brand-500/30 resize-none"
    />
  )
}

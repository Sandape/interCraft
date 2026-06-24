/**
 * AiOptimizePanel — M16 AI 简历优化 review UI.
 *
 * Adapts to the new `useResumeOptimize` state machine:
 *   idle → polling → waiting_patches → applying → done
 *                          ↓                ↓
 *                       error/timeout    error
 *
 * Per-patch: each patch has a checkbox to accept/reject. Bulk buttons
 * (全选/全不选) toggle the whole batch. On apply, accepted indices are
 * sent to the backend; on discard, nothing is persisted.
 */
import { useEffect, useState } from 'react'
import {
  Sparkles,
  Check,
  X,
  Loader2,
  Plus,
  Trash2,
  PencilLine,
  RotateCcw,
  AlertCircle,
  Clock,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Badge } from '@/components/ui/Badge'
import { useResumeOptimize, type ProposedPatch } from '@/modules/resume/hooks/useResumeOptimize'

interface AiOptimizePanelProps {
  branchId: string
  onOptimized?: (versionId: string) => void
}

const OP_META: Record<string, { label: string; variant: 'brand' | 'warning' | 'danger'; Icon: typeof PencilLine }> = {
  replace: { label: 'replace', variant: 'brand', Icon: PencilLine },
  add: { label: 'add', variant: 'warning', Icon: Plus },
  remove: { label: 'remove', variant: 'danger', Icon: Trash2 },
}

function defaultOpMeta(op: string) {
  return OP_META[op] ?? { label: op, variant: 'brand' as const, Icon: PencilLine }
}

function formatValue(v: unknown): string {
  if (v == null) return ''
  if (typeof v === 'string') return v
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

export default function AiOptimizePanel({ branchId, onOptimized }: AiOptimizePanelProps) {
  const [open, setOpen] = useState(false)
  const [jdInput, setJdInput] = useState('')

  const {
    status,
    loading,
    error,
    threadId,
    summary,
    patches,
    acceptedIndices,
    versionId,
    elapsedSec,
    start,
    cancel,
    togglePatch,
    acceptAll,
    rejectAll,
    apply,
    discard,
    reset,
  } = useResumeOptimize()

  // Reset hook state every time the modal closes so the next open is fresh.
  useEffect(() => {
    if (!open) reset()
  }, [open, reset])

  const handleStart = async () => {
    if (!jdInput.trim()) return
    await start({ branch_id: branchId, target_jd: jdInput.trim() })
  }

  const handleApply = async () => {
    const res = await apply()
    if (res?.version_id) onOptimized?.(res.version_id)
  }

  const handleDiscard = async () => {
    await discard()
  }

  const handleClose = () => {
    if (status === 'polling') cancel()
    setOpen(false)
  }

  const showInput = status === 'idle'
  const showPolling = status === 'polling'
  const showWaiting = status === 'waiting_patches'
  const showApplying = status === 'applying'
  const showDone = status === 'done'
  const showError = status === 'error'
  const showTimeout = status === 'timeout'

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        leftIcon={<Sparkles className="h-3.5 w-3.5" />}
        onClick={() => setOpen(true)}
        data-testid="ai-optimize-btn"
      >
        AI 优化
      </Button>

      <Modal
        open={open}
        onClose={handleClose}
        title="AI 简历优化"
        description="基于目标 JD 智能调整简历内容,可逐项接受或拒绝"
        size="lg"
      >
        {/* Idle: JD input */}
        {showInput && (
          <div className="space-y-3">
            <label className="block text-xs font-medium text-ink-2">目标职位描述 (JD)</label>
            <textarea
              value={jdInput}
              onChange={(e) => setJdInput(e.target.value)}
              placeholder="粘贴目标职位描述，或输入公司+职位名称..."
              rows={6}
              data-testid="ai-jd-input"
              className="w-full px-3 py-2 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            />
            <div className="flex items-center justify-end gap-2">
              <Button variant="ghost" onClick={handleClose} data-testid="ai-cancel-btn">
                取消
              </Button>
              <Button
                variant="primary"
                leftIcon={<Sparkles className="h-3.5 w-3.5" />}
                onClick={handleStart}
                disabled={!jdInput.trim()}
                data-testid="ai-start-btn"
              >
                开始分析
              </Button>
            </div>
          </div>
        )}

        {/* Polling: AI is working */}
        {showPolling && (
          <div className="flex flex-col items-center justify-center py-12 gap-3" data-testid="ai-polling">
            <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
            <p className="text-sm text-ink-1">AI 正在分析简历与目标 JD 的差距…</p>
            <div className="flex items-center gap-1.5 text-2xs text-ink-3">
              <Clock className="h-3 w-3" />
              <span>已等待 {elapsedSec}s / 60s</span>
            </div>
            <Button variant="ghost" size="sm" onClick={cancel} data-testid="ai-cancel-poll-btn">
              取消
            </Button>
          </div>
        )}

        {/* Waiting patches: per-patch review */}
        {showWaiting && (
          <div className="space-y-4" data-testid="ai-patches">
            {summary && (
              <div className="px-3 py-2 rounded-md bg-brand-50 dark:bg-brand-500/10 border border-brand-200/60 dark:border-brand-500/20">
                <p className="text-sm text-ink-1">{summary}</p>
              </div>
            )}

            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-ink-2">
                建议修改 ({acceptedIndices.size}/{patches.length})
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={acceptAll}
                  className="text-2xs text-brand-600 dark:text-brand-400 hover:underline"
                  data-testid="ai-accept-all-btn"
                >
                  全选
                </button>
                <span className="text-ink-3">·</span>
                <button
                  type="button"
                  onClick={rejectAll}
                  className="text-2xs text-ink-3 hover:underline"
                  data-testid="ai-reject-all-btn"
                >
                  全不选
                </button>
              </div>
            </div>

            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {patches.map((patch) => (
                <PatchRow
                  key={patch.index}
                  patch={patch}
                  accepted={acceptedIndices.has(patch.index)}
                  onToggle={() => togglePatch(patch.index)}
                />
              ))}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-surface-border dark:border-dark-surface-border">
              <Button
                variant="secondary"
                leftIcon={<X className="h-3.5 w-3.5" />}
                onClick={handleDiscard}
                data-testid="ai-discard-btn"
              >
                放弃
              </Button>
              <Button
                variant="primary"
                leftIcon={<Check className="h-3.5 w-3.5" />}
                onClick={handleApply}
                disabled={acceptedIndices.size === 0}
                data-testid="ai-apply-btn"
              >
                应用 ({acceptedIndices.size})
              </Button>
            </div>
          </div>
        )}

        {/* Applying */}
        {showApplying && (
          <div className="flex flex-col items-center justify-center py-12 gap-3" data-testid="ai-applying">
            <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
            <p className="text-sm text-ink-2">正在应用修改…</p>
          </div>
        )}

        {/* Done — apply success */}
        {showDone && versionId && (
          <div className="py-8 flex flex-col items-center gap-2" data-testid="ai-done-apply">
            <div className="h-10 w-10 rounded-full bg-success-50 dark:bg-success-500/10 flex items-center justify-center">
              <Check className="h-5 w-5 text-success-600 dark:text-success-400" />
            </div>
            <p className="text-sm font-medium text-ink-1">优化已应用</p>
            <p className="text-2xs text-ink-3">版本 ID: {versionId}</p>
          </div>
        )}

        {/* Done — discard */}
        {showDone && !versionId && (
          <div className="py-8 flex flex-col items-center gap-2" data-testid="ai-done-discard">
            <div className="h-10 w-10 rounded-full bg-surface-muted flex items-center justify-center">
              <X className="h-5 w-5 text-ink-3" />
            </div>
            <p className="text-sm text-ink-2">已放弃修改</p>
          </div>
        )}

        {/* Error */}
        {showError && error && (
          <div className="space-y-3" data-testid="ai-error">
            <div className="flex items-start gap-2 p-3 rounded bg-danger-50 dark:bg-danger-500/10 text-danger-600 dark:text-danger-400 text-sm">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
            <div className="flex justify-end">
              <Button
                variant="secondary"
                leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
                onClick={reset}
                data-testid="ai-retry-btn"
              >
                重试
              </Button>
            </div>
          </div>
        )}

        {/* Timeout */}
        {showTimeout && (
          <div className="space-y-3" data-testid="ai-timeout">
            <div className="flex items-start gap-2 p-3 rounded bg-warning-50 dark:bg-warning-500/10 text-warning-700 dark:text-warning-400 text-sm">
              <Clock className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error ?? '优化超时,请稍后重试'}</span>
            </div>
            <div className="flex justify-end">
              <Button
                variant="primary"
                leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
                onClick={reset}
                data-testid="ai-retry-timeout-btn"
              >
                重试
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  )
}

interface PatchRowProps {
  patch: ProposedPatch
  accepted: boolean
  onToggle: () => void
}

function PatchRow({ patch, accepted, onToggle }: PatchRowProps) {
  const meta = defaultOpMeta(patch.op)
  const Icon = meta.Icon
  const newValueText = formatValue(patch.value)
  const oldValueText = formatValue(patch.oldValue)

  return (
    <label
      className={`flex gap-3 p-3 rounded border cursor-pointer transition-colors ${
        accepted
          ? 'border-brand-300 dark:border-brand-500/40 bg-brand-50/40 dark:bg-brand-500/5'
          : 'border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface opacity-60'
      }`}
      data-testid={`ai-patch-${patch.index}`}
      data-accepted={accepted}
    >
      <input
        type="checkbox"
        checked={accepted}
        onChange={onToggle}
        className="mt-1 h-4 w-4 rounded border-surface-border text-brand-500 focus:ring-brand-500/30"
        data-testid={`ai-patch-checkbox-${patch.index}`}
      />
      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant={meta.variant} leftIcon={<Icon className="h-3 w-3" />}>
            {meta.label}
          </Badge>
          <code className="text-2xs text-ink-3 font-mono truncate">{patch.path}</code>
        </div>
        {oldValueText && (
          <div className="text-2xs text-ink-3 line-through whitespace-pre-wrap break-words max-h-16 overflow-y-auto pl-2 border-l-2 border-surface-border">
            {oldValueText}
          </div>
        )}
        {newValueText && (
          <div className="text-xs text-ink-1 whitespace-pre-wrap break-words max-h-24 overflow-y-auto pl-2 border-l-2 border-brand-400 dark:border-brand-500/50">
            {newValueText}
          </div>
        )}
      </div>
    </label>
  )
}

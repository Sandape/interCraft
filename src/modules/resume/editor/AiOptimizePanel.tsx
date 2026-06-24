/** AiOptimizePanel — M16 diff review UI for proposed patches. */
import { useState } from 'react'
import { Sparkles, Check, X, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { useResumeOptimize } from '@/modules/resume/hooks/useResumeOptimize'

interface AiOptimizePanelProps {
  branchId: string
  onOptimized?: (versionId: string) => void
}

export default function AiOptimizePanel({ branchId, onOptimized }: AiOptimizePanelProps) {
  const [open, setOpen] = useState(false)
  const [jdInput, setJdInput] = useState('')
  const { loading, error, status, proposedPatches, summary, threadId, versionId, start, confirm } = useResumeOptimize()

  const handleStart = async () => {
    if (!jdInput.trim()) return
    await start({ branch_id: branchId, target_jd: jdInput.trim() })
  }

  const handleApply = async () => {
    const res = await confirm('apply')
    if (res?.version_id) {
      onOptimized?.(res.version_id)
    }
  }

  const handleDiscard = async () => {
    await confirm('discard')
    setOpen(false)
  }

  const isInterrupted = status === 'waiting_interrupt'
  const isCompleted = status === 'completed' || versionId

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
        onClose={() => setOpen(false)}
        title="AI 简历优化"
        size="lg"
      >
        {!threadId && !loading && (
          <div className="space-y-3">
            <label className="block text-xs font-medium text-ink-2">目标职位描述 (JD)</label>
            <textarea
              value={jdInput}
              onChange={(e) => setJdInput(e.target.value)}
              placeholder="粘贴目标职位描述，或输入公司+职位名称..."
              rows={6}
              data-testid="ai-jd-input"
              className="w-full px-3 py-2 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1 resize-none"
            />
            <Button
              variant="primary"
              leftIcon={loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              onClick={handleStart}
              disabled={loading || !jdInput.trim()}
            >
              {loading ? '分析中…' : '开始分析'}
            </Button>
          </div>
        )}

        {loading && !isInterrupted && !isCompleted && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
            <span className="ml-2 text-sm text-ink-2">AI 正在分析简历与目标 JD 的差距…</span>
          </div>
        )}

        {error && (
          <div className="p-3 rounded bg-danger-50 dark:bg-danger-500/10 text-danger-600 dark:text-danger-400 text-sm">
            {error}
          </div>
        )}

        {isInterrupted && proposedPatches && proposedPatches.length > 0 && (
          <div className="space-y-4">
            {summary && (
              <p className="text-sm text-ink-2">{summary}</p>
            )}
            <div className="space-y-2">
              <p className="text-xs font-medium text-ink-2">建议修改 ({proposedPatches.length} 项)</p>
              {proposedPatches.map((patch, idx) => (
                <div key={idx} className="p-3 rounded border border-surface-border dark:border-dark-surface-border text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="default">{String(patch.op || 'replace')}</Badge>
                    <code className="text-2xs text-ink-3">{String(patch.path || '')}</code>
                  </div>
                  <div className="text-xs text-ink-2 whitespace-pre-wrap max-h-24 overflow-y-auto">
                    {String(patch.value || '')}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                leftIcon={<Check className="h-3.5 w-3.5" />}
                onClick={handleApply}
              >
                应用修改
              </Button>
              <Button
                variant="secondary"
                leftIcon={<X className="h-3.5 w-3.5" />}
                onClick={handleDiscard}
              >
                放弃
              </Button>
            </div>
          </div>
        )}

        {isCompleted && versionId && (
          <div className="py-6 text-center">
            <Check className="h-8 w-8 text-success-500 mx-auto mb-2" />
            <p className="text-sm font-medium text-ink-1">优化已应用</p>
            <p className="text-2xs text-ink-3 mt-1">版本 ID: {versionId}</p>
          </div>
        )}

        {isCompleted && !versionId && (
          <div className="py-6 text-center">
            <X className="h-8 w-8 text-ink-3 mx-auto mb-2" />
            <p className="text-sm text-ink-2">已放弃修改</p>
          </div>
        )}
      </Modal>
    </>
  )
}

// Need to import Badge for the patch display
import { Badge } from '@/components/ui/Badge'

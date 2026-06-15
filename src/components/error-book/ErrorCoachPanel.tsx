/** ErrorCoachPanel — M17 error question reinforcement dialog. */
import { useState, useCallback } from 'react'
import { X, Send, Loader2, CheckCircle, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { useErrorCoach } from '@/hooks/useErrorCoach'

interface ErrorCoachPanelProps {
  errorQuestionId: string
  questionText: string
  open: boolean
  onClose: () => void
}

export default function ErrorCoachPanel({ errorQuestionId, questionText, open, onClose }: ErrorCoachPanelProps) {
  const [answer, setAnswer] = useState('')
  const {
    loading,
    status,
    correctCount,
    hintLevel,
    score,
    error,
    start,
    submitAnswer,
    abort,
    reset,
  } = useErrorCoach()

  const handleStart = useCallback(async () => {
    await start(errorQuestionId)
  }, [errorQuestionId, start])

  const handleSubmitAnswer = useCallback(async () => {
    if (!answer.trim()) return
    await submitAnswer(answer.trim())
    setAnswer('')
  }, [answer, submitAnswer])

  const handleClose = useCallback(() => {
    abort()
    reset()
    onClose()
  }, [abort, reset, onClose])

  const isComplete = status === 'completed' || status === 'aborted'
  const isRunning = status === 'running'

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="错题强化"
      size="md"
    >
      <div className="space-y-4">
        {/* Question */}
        <div className="p-3 rounded bg-surface-muted dark:bg-dark-surface-muted">
          <p className="text-xs font-medium text-ink-2 mb-1">题目</p>
          <p className="text-sm text-ink-1">{questionText}</p>
        </div>

        {/* Progress */}
        {isRunning && (
          <div className="flex items-center gap-3 text-xs text-ink-2">
            <span>正确次数: {correctCount}/3</span>
            {hintLevel && <span>提示等级: {hintLevel}</span>}
            {score !== null && (
              <span className={score >= 8 ? 'text-success-500' : 'text-danger-500'}>
                得分: {score}/10
              </span>
            )}
          </div>
        )}

        {/* Start button */}
        {!status && !loading && (
          <div className="text-center py-4">
            <Button variant="primary" onClick={handleStart} data-testid="coach-start-button">
              开始强化
            </Button>
          </div>
        )}

        {/* Loading */}
        {loading && !isComplete && (
          <div className="flex items-center justify-center py-4" data-testid="coach-loading">
            <Loader2 className="h-5 w-5 animate-spin text-brand-500" />
          </div>
        )}

        {/* Answer input */}
        {isRunning && (
          <div className="space-y-2" data-testid="coach-answer-form">
            <label className="block text-xs font-medium text-ink-2">你的回答</label>
            <div className="flex gap-2">
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="输入你的理解和答案..."
                rows={3}
                className="flex-1 px-3 py-2 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1 resize-none"
                data-testid="coach-answer-input"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSubmitAnswer()
                  }
                }}
              />
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Send className="h-3.5 w-3.5" />}
                onClick={handleSubmitAnswer}
                disabled={!answer.trim() || loading}
                className="self-end"
                data-testid="coach-submit-answer"
              >
                提交
              </Button>
            </div>
          </div>
        )}

        {/* Complete state */}
        {isComplete && (
          <div className="py-4 text-center" data-testid="coach-complete">
            {correctCount >= 3 ? (
              <>
                <CheckCircle className="h-8 w-8 text-success-500 mx-auto mb-2" />
                <p className="text-sm font-medium text-ink-1">已掌握！</p>
                <p className="text-2xs text-ink-3 mt-1">答对 {correctCount} 题，本题 frequency 已递减</p>
              </>
            ) : (
              <>
                <AlertTriangle className="h-8 w-8 text-ink-3 mx-auto mb-2" />
                <p className="text-sm text-ink-2">已退出</p>
                <p className="text-2xs text-ink-3 mt-1">本次答对 {correctCount} 题</p>
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="text-xs text-danger-500">{error}</p>
        )}
      </div>
    </Modal>
  )
}

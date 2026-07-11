/** GeneralCoach page — M19 + REQ-061 T087. */
import { useState, useCallback, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Send, Bot, User, X, Loader2, Sparkles, ThumbsUp, ThumbsDown, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useGeneralCoach, type ChatMessage } from '@/hooks/useGeneralCoach'

export default function GeneralCoach() {
  const [input, setInput] = useState('')
  const {
    loading,
    messages,
    detectedIntent,
    redirectTo,
    error,
    taskId,
    availableActions,
    pointSummary,
    start,
    sendMessage,
    close,
    reset,
    recover,
    submitFeedback,
  } = useGeneralCoach()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = useCallback(() => {
    const el = messagesEndRef.current
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth' })
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSend = useCallback(async () => {
    if (!input.trim()) return
    const text = input.trim()
    setInput('')
    await sendMessage(text)
  }, [input, sendMessage])

  const handleStart = useCallback(async () => {
    if (!input.trim()) return
    const text = input.trim()
    setInput('')
    await start(text)
  }, [input, start])

  const handleClose = useCallback(async () => {
    await close()
    reset()
  }, [close, reset])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (messages.length === 0 && !loading) handleStart()
      else handleSend()
    }
  }

  return (
    <div className="h-full flex flex-col max-w-4xl mx-auto">
      <div className="flex items-center justify-between px-6 py-3 border-b border-surface-border dark:border-dark-surface-border">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-brand-500" />
          <h1 className="text-base font-semibold text-ink-1">AI 面试教练</h1>
          {pointSummary && (
            <span className="text-xs text-ink-3" data-testid="coach-point-summary">
              点数 {pointSummary.settled ?? 0}/{pointSummary.quoted_max ?? pointSummary.reserved ?? '—'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {taskId && (
            <Link to={`/ai-tasks/${encodeURIComponent(taskId)}`} className="text-xs text-brand-600 underline" data-testid="coach-task-link">
              AI 任务
            </Link>
          )}
          {availableActions.includes('resume') && (
            <Button variant="ghost" size="sm" leftIcon={<RotateCcw className="h-3.5 w-3.5" />} onClick={() => void recover()} data-testid="coach-recover">
              恢复
            </Button>
          )}
          {(messages.length > 0 || availableActions.includes('cancel')) && (
            <Button variant="ghost" size="sm" leftIcon={<X className="h-3.5 w-3.5" />} onClick={handleClose} data-testid="coach-close">
              结束对话
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center" data-testid="coach-empty-state">
            <Sparkles className="h-10 w-10 text-brand-500/50 mb-3" />
            <h2 className="text-lg font-medium text-ink-1 mb-1">有什么可以帮助你的？</h2>
            <p className="text-sm text-ink-3 max-w-md">我可以帮你准备面试、优化简历、提供职业发展建议，或回答技术问题。</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} data-testid={`message-${msg.role}`}>
            <MessageBubble
              message={msg}
              onFeedback={
                msg.role === 'assistant' && typeof msg.turnIndex === 'number'
                  ? (rating) => void submitFeedback(msg.turnIndex!, rating)
                  : undefined
              }
            />
          </div>
        ))}

        {loading && (
          <div className="flex items-start gap-2" data-testid="coach-loading">
            <Bot className="h-5 w-5 text-brand-500 mt-1 flex-shrink-0" />
            <div className="px-3 py-2 rounded-lg bg-surface-muted dark:bg-dark-surface-muted">
              <Loader2 className="h-4 w-4 animate-spin text-brand-500" />
            </div>
          </div>
        )}

        {redirectTo && (
          <div className="p-3 rounded bg-brand-50 dark:bg-brand-500/10 border border-brand-200 dark:border-brand-500/30 text-sm text-ink-1" data-testid="coach-redirect">
            检测到您的问题属于「{redirectTo}」范畴，建议使用对应功能获得更专业的帮助。
          </div>
        )}

        {detectedIntent && (
          <div className="text-2xs text-ink-3 text-right" data-testid="coach-intent">意图：{detectedIntent}</div>
        )}

        {error && (
          <div className="p-3 rounded bg-danger-50 dark:bg-danger-500/10 text-danger-600 dark:text-danger-400 text-sm" data-testid="coach-error">
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="px-6 py-3 border-t border-surface-border dark:border-dark-surface-border">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题..."
            rows={2}
            data-testid="coach-input"
            className="flex-1 px-3 py-2 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1 resize-none"
          />
          <Button
            variant="primary"
            size="sm"
            leftIcon={<Send className="h-3.5 w-3.5" />}
            onClick={messages.length === 0 ? handleStart : handleSend}
            disabled={!input.trim() || loading}
            className="self-end"
            data-testid="coach-send"
          >
            {messages.length === 0 ? '开始' : '发送'}
          </Button>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({
  message,
  onFeedback,
}: {
  message: ChatMessage
  onFeedback?: (rating: 'up' | 'down') => void
}) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex items-start gap-2 ${isUser ? 'flex-row-reverse' : ''}`}>
      {isUser ? <User className="h-5 w-5 text-ink-3 mt-1 flex-shrink-0" /> : <Bot className="h-5 w-5 text-brand-500 mt-1 flex-shrink-0" />}
      <div
        className={`px-3 py-2 rounded-lg text-sm max-w-[80%] ${
          isUser ? 'bg-brand-500 text-white' : 'bg-surface-muted dark:bg-dark-surface-muted text-ink-1'
        }`}
        data-testid={isUser ? 'coach-user-bubble' : 'coach-assistant-bubble'}
      >
        {message.content}
        {!isUser && onFeedback && (
          <div className="mt-2 flex gap-2" data-testid="coach-answer-feedback">
            <button type="button" aria-label="有用" onClick={() => onFeedback('up')}>
              <ThumbsUp className={`h-3.5 w-3.5 ${message.feedback === 'up' ? 'text-brand-600' : 'text-ink-3'}`} />
            </button>
            <button type="button" aria-label="无用" onClick={() => onFeedback('down')}>
              <ThumbsDown className={`h-3.5 w-3.5 ${message.feedback === 'down' ? 'text-brand-600' : 'text-ink-3'}`} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

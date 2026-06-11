import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  Send,
  Mic,
  MicOff,
  Lightbulb,
  Timer,
  Clock,
  Sparkles,
  ChevronRight,
  Pause,
  Square,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  BarChart3,
  Code,
  ThumbsUp,
  MessageSquare,
  MoreHorizontal,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { Avatar } from '@/components/ui/Avatar'
import { cn } from '@/lib/utils'

interface Message {
  id: string
  role: 'interviewer' | 'candidate'
  content: string
  timestamp: number
  feedback?: {
    score: number
    strengths: string[]
    improvements: string[]
  }
  thinking?: boolean
}

const initialMessages: Message[] = [
  {
    id: 'm-1',
    role: 'interviewer',
    content:
      '你好，我是今天的面试官 Kevin。我们会进行大约 40 分钟的面试，主要围绕你的项目经验和技术深度展开。请先简单介绍一下你自己，并重点说说最有代表性的一个项目。',
    timestamp: 0,
  },
]

const nextQuestions: { id: string; question: string; dimension: string }[] = [
  { id: 'q-2', question: '能详细讲讲这个微前端框架的沙箱隔离机制吗？', dimension: '技术深度' },
  { id: 'q-3', question: '如果让你重新设计 EdgeKit，会做哪些改进？', dimension: '系统设计' },
  { id: 'q-4', question: 'TypeScript 在你们项目中遇到过哪些类型设计挑战？', dimension: '工程实践' },
]

export default function InterviewLive() {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const [currentQ, setCurrentQ] = useState(1)
  const totalQ = 8
  const [elapsed, setElapsed] = useState(125) // 02:05
  const [thinkingMode, setThinkingMode] = useState(true)
  const [hintOpen, setHintOpen] = useState(false)
  const [aiThinking, setAiThinking] = useState(false)
  const [muted, setMuted] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const id = setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const sendMessage = () => {
    if (!input.trim()) return
    const userMsg: Message = {
      id: `m-${Date.now()}`,
      role: 'candidate',
      content: input,
      timestamp: elapsed,
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setAiThinking(true)

    // 模拟 AI 反馈
    setTimeout(() => {
      const interviewerMsg: Message = {
        id: `m-${Date.now() + 1}`,
        role: 'interviewer',
        content: nextQuestions[currentQ - 1]?.question || '能展开说说具体的实现细节吗？',
        timestamp: elapsed + 30,
        feedback: {
          score: 82,
          strengths: ['回答结构清晰，有 STAR 法则的影子', '主动量化了项目成果'],
          improvements: ['可以更深入地讲技术选型的权衡', 'EdgeKit 性能数据需要更具体'],
        },
      }
      setMessages((prev) => [...prev, interviewerMsg])
      setCurrentQ((q) => Math.min(q + 1, totalQ))
      setAiThinking(false)
    }, 1800)
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
  }

  return (
    <div className="h-full flex bg-surface-subtle dark:bg-dark-surface-subtle">
      {/* 主对话区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部进度条 */}
        <div className="bg-surface dark:bg-dark-surface border-b border-surface-border dark:border-dark-surface-border px-6 py-3 flex-shrink-0">
          <div className="flex items-center gap-4">
            <Link
              to="/interview"
              className="p-1 -ml-1 rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>

            <div className="flex items-center gap-2.5 min-w-0">
              <Avatar name="Kevin" size="sm" />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-ink-1 truncate">Kevin · 高级技术面试官</span>
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-2xs text-emerald-600 dark:text-emerald-400">在线</span>
                </div>
                <div className="text-2xs text-ink-3">字节跳动 · 电商前端 · 高级工程师模拟面试</div>
              </div>
            </div>

            <div className="flex-1 max-w-md mx-4">
              <div className="flex items-center justify-between text-2xs mb-1">
                <span className="text-ink-3">
                  进度 · 第 <span className="text-ink-1 font-medium">{currentQ}</span> / {totalQ} 题
                </span>
                <span className="text-ink-3">
                  当前维度：
                  <span className="text-ink-1 font-medium ml-0.5">{nextQuestions[currentQ - 1]?.dimension || '—'}</span>
                </span>
              </div>
              <Progress value={(currentQ / totalQ) * 100} size="sm" variant="brand" />
            </div>

            <div className="flex items-center gap-1.5 flex-shrink-0">
              <Badge variant="default" leftIcon={<Clock className="h-2.5 w-2.5" />}>
                {formatTime(elapsed)}
              </Badge>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={muted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
                onClick={() => setMuted((v) => !v)}
              >
                {muted ? '已静音' : '语音'}
              </Button>
              <Button size="sm" variant="ghost" leftIcon={<Pause className="h-3.5 w-3.5" />}>
                暂停
              </Button>
              <Button size="sm" variant="danger" leftIcon={<Square className="h-3.5 w-3.5" />}>
                结束
              </Button>
            </div>
          </div>
        </div>

        {/* 消息流 */}
        <div ref={messagesRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {/* 面试开场 - 特殊卡片 */}
          {messages[0] && (
            <div className="flex gap-3 max-w-3xl">
              <Avatar name="Kevin" size="md" />
              <div className="flex-1 min-w-0">
                <div className="text-xs text-ink-3 mb-1.5">Kevin · 开场</div>
                <div className="inline-block px-4 py-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border text-sm text-ink-1 leading-relaxed shadow-notion-sm">
                  {messages[0].content}
                </div>
              </div>
            </div>
          )}

          {messages.slice(1).map((m, idx) => (
            <MessageBubble key={m.id} message={m} index={idx} />
          ))}

          {/* AI 思考中 */}
          {aiThinking && (
            <div className="flex gap-3 max-w-3xl">
              <Avatar name="Kevin" size="md" />
              <div className="flex-1 min-w-0">
                <div className="text-xs text-ink-3 mb-1.5 flex items-center gap-1.5">
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                  面试官正在评估你的回答
                </div>
                <div className="inline-flex items-center gap-1.5 px-4 py-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border">
                  <div className="flex gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="h-1.5 w-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="h-1.5 w-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 输入区 */}
        <div className="border-t border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface px-6 py-3 flex-shrink-0">
          {/* 思考提示 */}
          {thinkingMode && (
            <div className="mb-2 flex items-center gap-2 text-2xs text-ink-3">
              <Lightbulb className="h-3 w-3 text-amber-500" />
              <span>建议先思考 30 秒再回答 · 当前问题考察「{nextQuestions[currentQ - 1]?.dimension || '—'}」</span>
              <button
                onClick={() => setHintOpen((v) => !v)}
                className="ml-auto text-brand-600 dark:text-brand-300 hover:underline"
              >
                {hintOpen ? '隐藏提示' : '查看提示'}
              </button>
            </div>
          )}
          {hintOpen && (
            <div className="mb-2 p-2.5 rounded-md bg-amber-50/60 dark:bg-amber-500/10 border border-amber-200/40 dark:border-amber-500/20 text-xs text-ink-2 leading-relaxed">
              <span className="font-medium text-amber-700 dark:text-amber-400">💡 回答思路：</span>
              从「问题背景 → 方案选型 → 核心实现 → 效果验证」四个角度回答，
              重点展示 EdgeKit 与 qiankun 的对比数据，量化收益。
            </div>
          )}

          <div className="flex items-end gap-2">
            <button
              className="h-9 w-9 rounded-md text-ink-3 hover:bg-surface-muted hover:text-ink-1 transition-colors flex items-center justify-center flex-shrink-0"
              aria-label="语音输入"
            >
              <Mic className="h-4 w-4" />
            </button>
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendMessage()
                  }
                }}
                placeholder="输入你的回答…（Enter 发送，Shift+Enter 换行）"
                rows={1}
                className="w-full px-3 py-2 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:bg-surface dark:focus:bg-dark-surface resize-none max-h-32 transition-all"
                style={{ minHeight: '36px' }}
              />
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              <Button
                size="md"
                variant="ghost"
                leftIcon={<Sparkles className="h-3.5 w-3.5" />}
                onClick={() => setHintOpen((v) => !v)}
              >
                AI 润色
              </Button>
              <Button
                size="md"
                variant="primary"
                leftIcon={<Send className="h-3.5 w-3.5" />}
                onClick={sendMessage}
                disabled={!input.trim()}
              >
                发送
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* 右侧实时反馈面板 */}
      <aside className="w-72 border-l border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface flex flex-col flex-shrink-0">
        <div className="px-4 py-3 border-b border-surface-border dark:border-dark-surface-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-brand-500" />
            <span className="text-sm font-semibold text-ink-1">实时反馈</span>
          </div>
          <button className="text-2xs text-ink-3 hover:text-ink-1 transition-colors">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* 当前评分 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs text-ink-3">当前综合评分</div>
              <Badge variant="success" leftIcon={<ThumbsUp className="h-2.5 w-2.5" />}>
                良好
              </Badge>
            </div>
            <div className="text-center py-3 rounded-md bg-gradient-to-br from-brand-50 to-surface dark:from-brand-500/10 dark:to-dark-surface border border-surface-border dark:border-dark-surface-border">
              <div className="text-3xl font-semibold text-ink-1 tabular-nums">82</div>
              <div className="text-2xs text-ink-3 mt-0.5">/ 100 分</div>
            </div>
          </div>

          {/* 五维表现 */}
          <div>
            <div className="text-xs text-ink-3 mb-2">维度表现</div>
            <div className="space-y-2">
              {[
                { name: '技术深度', score: 85 },
                { name: '系统设计', score: 78 },
                { name: '工程实践', score: 88 },
                { name: '沟通表达', score: 80 },
                { name: '算法能力', score: 82 },
              ].map((d) => (
                <div key={d.name} className="space-y-1">
                  <div className="flex items-center justify-between text-2xs">
                    <span className="text-ink-2">{d.name}</span>
                    <span
                      className={cn(
                        'font-semibold tabular-nums',
                        d.score >= 85
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : d.score >= 75
                            ? 'text-brand-600 dark:text-brand-300'
                            : 'text-amber-600 dark:text-amber-400',
                      )}
                    >
                      {d.score}
                    </span>
                  </div>
                  <Progress
                    value={d.score}
                    size="sm"
                    variant={d.score >= 85 ? 'success' : d.score >= 75 ? 'brand' : 'warning'}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* 上一题反馈 */}
          <div>
            <div className="text-xs text-ink-3 mb-2">上一题反馈</div>
            <div className="p-3 rounded-md bg-surface-muted dark:bg-dark-surface-muted space-y-2">
              <div>
                <div className="text-2xs font-medium text-emerald-600 dark:text-emerald-400 mb-1 flex items-center gap-1">
                  <CheckCircle2 className="h-2.5 w-2.5" />
                  亮点
                </div>
                <ul className="space-y-0.5 text-2xs text-ink-2">
                  <li className="flex gap-1.5">
                    <span className="text-ink-muted">•</span>
                    <span>回答结构清晰，有 STAR 法则影子</span>
                  </li>
                  <li className="flex gap-1.5">
                    <span className="text-ink-muted">•</span>
                    <span>主动量化了项目成果</span>
                  </li>
                </ul>
              </div>
              <div>
                <div className="text-2xs font-medium text-amber-600 dark:text-amber-400 mb-1 flex items-center gap-1">
                  <AlertCircle className="h-2.5 w-2.5" />
                  改进
                </div>
                <ul className="space-y-0.5 text-2xs text-ink-2">
                  <li className="flex gap-1.5">
                    <span className="text-ink-muted">•</span>
                    <span>深入讲技术选型权衡</span>
                  </li>
                  <li className="flex gap-1.5">
                    <span className="text-ink-muted">•</span>
                    <span>EdgeKit 性能数据更具体</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* 题目导航 */}
          <div>
            <div className="text-xs text-ink-3 mb-2">题目进度</div>
            <div className="grid grid-cols-4 gap-1.5">
              {Array.from({ length: totalQ }).map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    'aspect-square rounded text-xs font-medium flex items-center justify-center transition-all',
                    i + 1 < currentQ
                      ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                      : i + 1 === currentQ
                        ? 'bg-brand-500 text-white shadow-notion-sm'
                        : 'bg-surface-muted dark:bg-dark-surface-muted text-ink-3',
                  )}
                >
                  {i + 1}
                </div>
              ))}
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}

function MessageBubble({ message }: { message: Message; index: number }) {
  if (message.role === 'interviewer') {
    return (
      <div className="flex gap-3 max-w-3xl">
        <Avatar name="Kevin" size="md" />
        <div className="flex-1 min-w-0">
          <div className="text-xs text-ink-3 mb-1.5 flex items-center gap-1.5">
            Kevin
            <span className="text-ink-muted">· 面试官</span>
          </div>
          <div className="inline-block px-4 py-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border text-sm text-ink-1 leading-relaxed shadow-notion-sm">
            {message.content}
          </div>
          {message.feedback && (
            <div className="mt-2.5 grid grid-cols-2 gap-2 max-w-2xl">
              <FeedbackPanel
                title="亮点"
                tone="success"
                icon={<CheckCircle2 className="h-3 w-3" />}
                items={message.feedback.strengths}
              />
              <FeedbackPanel
                title="可改进"
                tone="warning"
                icon={<AlertCircle className="h-3 w-3" />}
                items={message.feedback.improvements}
              />
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3 max-w-3xl ml-auto justify-end">
      <div className="flex-1 min-w-0 flex flex-col items-end">
        <div className="text-xs text-ink-3 mb-1.5 flex items-center gap-1.5">
          <span>你</span>
          <span className="text-ink-muted">· 候选人</span>
        </div>
        <div className="inline-block px-4 py-3 rounded-lg rounded-tr-sm bg-brand-500 text-white text-sm leading-relaxed max-w-xl">
          {message.content}
        </div>
      </div>
      <Avatar name="浩然" size="md" />
    </div>
  )
}

function FeedbackPanel({
  title,
  tone,
  icon,
  items,
}: {
  title: string
  tone: 'success' | 'warning'
  icon: React.ReactNode
  items: string[]
}) {
  return (
    <div
      className={cn(
        'p-2.5 rounded-md border text-xs',
        tone === 'success'
          ? 'bg-emerald-50/60 dark:bg-emerald-500/5 border-emerald-200/40 dark:border-emerald-500/20'
          : 'bg-amber-50/60 dark:bg-amber-500/5 border-amber-200/40 dark:border-amber-500/20',
      )}
    >
      <div
        className={cn(
          'flex items-center gap-1 mb-1 font-medium',
          tone === 'success'
            ? 'text-emerald-700 dark:text-emerald-400'
            : 'text-amber-700 dark:text-amber-400',
        )}
      >
        {icon}
        {title}
      </div>
      <ul className="space-y-0.5 text-ink-2 dark:text-dark-ink-secondary">
        {items.map((it, i) => (
          <li key={i} className="flex gap-1.5">
            <span className="text-ink-muted">•</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

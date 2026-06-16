import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Send,
  Mic,
  Timer,
  Clock,
  Sparkles,
  Pause,
  Square,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  BarChart3,
  ThumbsUp,
  Lightbulb,
  Volume2,
  VolumeX,
  Briefcase,
  Building2,
  Play,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { Avatar } from '@/components/ui/Avatar'
import { useAvatarBlob } from '@/hooks/queries/useAvatarBlob'
import { cn } from '@/lib/utils'
import { useInterviewWS, type WSEvent } from '@/hooks/useInterviewWS'
import { useAuthStore } from '@/stores/useAuthStore'
import { interviewSessionRepo } from '@/repositories/interviewSessionRepo'
import { getAccessToken } from '@/api/token-storage'
import { ErrorBanner } from '@/components/interview/ErrorBanner'
import { StreamingText } from '@/components/interview/StreamingText'
import { ProgressBar } from '@/components/interview/ProgressBar'

const TOTAL_QUESTIONS = 5
const INTERVIEWER_NAME = 'AI 面试官'

interface QuestionData {
  question: string
  dimension: string
  expected_points: string[]
  hints: string[]
}

interface ScoreData {
  question_no: number
  score: number
  dimension: string
  feedback: string
  sub_scores: Record<string, number>
}

interface ReportData {
  overall_score: number
  report_id: string
}

function uniqueBy<T>(items: T[], keyOf: (item: T) => string): T[] {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = keyOf(item)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export default function InterviewLive() {
  const token = getAccessToken()
  const { id: routeSessionId } = useParams<{ id: string }>()
  const currentUser = useAuthStore((s) => s.user)
  const userAvatarUrl = useAvatarBlob(currentUser?.avatar_url ?? null) ?? undefined
  const userDisplayName =
    currentUser?.display_name || currentUser?.email.split('@')[0] || 'You'

  // ---- phase state ----
  const [phase, setPhase] = useState<'setup' | 'connecting' | 'live' | 'completed' | 'resume_error'>(
    routeSessionId ? 'connecting' : 'setup',
  )
  const [position, setPosition] = useState('')
  const [company, setCompany] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(routeSessionId || null)
  const [setupError, setSetupError] = useState<string | null>(null)
  const [resumedNotice, setResumedNotice] = useState(false)

  // ---- interview state ----
  const [input, setInput] = useState('')
  const [muted, setMuted] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [aiThinking, setAiThinking] = useState(false)
  const [sequenceNo, setSequenceNo] = useState(0)

  // accumulated from WS events
  const [questions, setQuestions] = useState<QuestionData[]>([])
  const [scores, setScores] = useState<ScoreData[]>([])
  const [report, setReport] = useState<ReportData | null>(null)

  // track user answers locally
  const [userAnswers, setUserAnswers] = useState<Array<{ content: string; seqNo: number }>>([])

  const messagesRef = useRef<HTMLDivElement>(null)

  // ---- WebSocket ----
  const ws = useInterviewWS(token || '')

  // ---- accumulate WS events into interview state ----
  const lastProcessedRef = useRef(0)

  useEffect(() => {
    const events = ws.state.events
    if (events.length <= lastProcessedRef.current) return

    for (let i = lastProcessedRef.current; i < events.length; i++) {
      const evt = events[i]
      processEvent(evt)
    }
    lastProcessedRef.current = events.length
  }, [ws.state.events])

  const processEvent = useCallback((evt: WSEvent) => {
    switch (evt.type) {
      case 'node.completed': {
        const summary = evt.payload.summary || {}
        if (evt.node_name === 'score' && summary.score > 0) {
          setScores((prev) => {
            if (prev.some((s) => s.question_no === summary.question_no)) return prev
            return [...prev, {
              question_no: summary.question_no,
              score: summary.score,
              dimension: summary.dimension || '',
              feedback: summary.feedback || '',
              sub_scores: summary.sub_scores || {},
            }]
          })
        }
        if (evt.node_name === 'question_gen' && summary.question) {
          setQuestions((prev) => {
            if (prev.some((q) => q.question === summary.question)) return prev
            return [...prev, {
              question: summary.question,
              dimension: summary.dimension || '',
              expected_points: summary.expected_points || [],
              hints: summary.hints || [],
            }]
          })
        }
        if (evt.node_name === 'report') {
          setReport({
            overall_score: summary.overall_score || 0,
            report_id: summary.report_id || '',
          })
          setPhase('completed')
        }
        break
      }
      case 'error': {
        setAiThinking(false)
        break
      }
    }
  }, [])

  // ---- timer ----
  useEffect(() => {
    if (phase !== 'live') return
    const id = setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => clearInterval(id)
  }, [phase])

  // ---- auto-scroll ----
  useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: 'smooth' })
  }, [questions, scores, ws.state.streamingText, userAnswers, aiThinking])

  // ---- setup: create session + start + connect WS ----
  const handleSetup = async () => {
    if (!position.trim() || !company.trim()) return
    setSetupError(null)
    setPhase('connecting')

    try {
      const created = await interviewSessionRepo.create({
        position: position.trim(),
        company: company.trim(),
        mode: 'text',
      })
      const sid = created.data.id

      await interviewSessionRepo.start(sid)
      setSessionId(sid)
      ws.connect()
      setPhase('live')
    } catch (err: any) {
      setSetupError(err?.message || '创建面试失败')
      setPhase('setup')
    }
  }

  // ---- resume: when /interview/:id/live, restore state and connect WS ----
  const resumeRanRef = useRef(false)
  useEffect(() => {
    if (!routeSessionId || resumeRanRef.current) return
    resumeRanRef.current = true

    const restore = async () => {
      try {
        const sess = await interviewSessionRepo.getById(routeSessionId)
        if (sess.status === 'completed') {
          // Already finished — go straight to report view
          setPosition(sess.position || '')
          setCompany(sess.company || '')
          setSessionId(routeSessionId)
          setPhase('completed')
          setReport({ overall_score: Number(sess.overall_score || 0), report_id: '' })
          return
        }

        const resumed = await interviewSessionRepo.resume(routeSessionId)
        const values = resumed.data?.values || {}
        const restoredQuestions = (values.questions || []) as any[]
        const restoredScores = (values.scores || []) as any[]
        const messages = (values.messages || []) as any[]

        const userMessages = messages
          .filter((m: any) => {
            if (m && typeof m === 'object') {
              return m.role === 'user' || m.type === 'human'
            }
            return false
          })
          .map((m: any) => (typeof m.content === 'string' ? m.content : ''))

        setPosition(sess.position || '')
        setCompany(sess.company || '')

        setQuestions(
          uniqueBy(restoredQuestions, (q: any) => q?.question || '').map((q: any) => ({
            question: q.question || '',
            dimension: q.dimension || '',
            expected_points: q.expected_points || [],
            hints: q.hints || [],
          })),
        )

        setScores(
          uniqueBy(restoredScores, (s: any) => String(s?.question_no || s?.sequence_no || '')).map((s: any) => ({
            question_no: s.question_no || s.sequence_no || 0,
            score: s.score || 0,
            dimension: s.dimension || '',
            feedback: s.feedback || '',
            sub_scores: s.sub_scores || {},
          })),
        )

        const reconstructedAnswers = userMessages.map((content, idx) => ({
          content,
          seqNo: idx,
        }))
        setUserAnswers(reconstructedAnswers)
        setSequenceNo(reconstructedAnswers.length)

        if (sess.duration_sec) setElapsed(sess.duration_sec)

        setSessionId(routeSessionId)
        setResumedNotice(true)
        ws.connect()
        setPhase('live')
      } catch (err: any) {
        // Don't fall back to the empty setup form — that loses all context.
        // Show a dedicated error page with the session id and a retry action.
        console.error('[interview-live] resume failed', err)
        setResumeErrorMsg(err?.message || '恢复面试失败,请稍后重试')
        setPhase('resume_error')
      }
    }

    restore()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeSessionId])

  const [resumeErrorMsg, setResumeErrorMsg] = useState<string | null>(null)
  const [resumeRetrying, setResumeRetrying] = useState(false)
  const handleRetryResume = useCallback(() => {
    // Force a full page reload — the resume effect is gated by
    // `resumeRanRef` (which is reset on mount), so a refresh is the
    // simplest way to retry the session restore.
    if (!routeSessionId) return
    window.location.assign(`/interview/${routeSessionId}/live`)
  }, [routeSessionId])

  // ---- submit answer ----
  const submitAnswer = () => {
    if (!input.trim() || !sessionId) return

    const seq = sequenceNo
    setUserAnswers((prev) => [...prev, { content: input, seqNo: seq }])
    setInput('')
    setAiThinking(true)
    setSequenceNo((n) => n + 1)

    ws.submitAnswer(sessionId, input, seq)
  }

  // clear aiThinking when question starts streaming or score completes
  useEffect(() => {
    if (ws.state.currentNode === 'question_gen' && ws.state.streamingText) {
      setAiThinking(false)
    }
  }, [ws.state.currentNode, ws.state.streamingText])

  // clear aiThinking on error
  useEffect(() => {
    if (ws.state.error) setAiThinking(false)
  }, [ws.state.error])

  // ---- derived data ----
  const currentQuestionIndex = questions.length // how many questions received
  const lastScore = scores.length > 0 ? scores[scores.length - 1] : null
  const avgScore = scores.length > 0
    ? Math.round(scores.reduce((s, sc) => s + sc.score, 0) / scores.length)
    : 0

  // dimension scores for sidebar
  const dimensionScores: Record<string, number[]> = {}
  scores.forEach((s) => {
    if (!dimensionScores[s.dimension]) dimensionScores[s.dimension] = []
    dimensionScores[s.dimension].push(s.score)
  })
  const dimensionAverages = Object.entries(dimensionScores).map(([dim, vals]) => ({
    name: dim,
    score: Math.round(vals.reduce((a, b) => a + b, 0) / vals.length),
  }))

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
  }

  const lastQuestion = questions.length > 0 ? questions[questions.length - 1] : null

  // ---- resume_error phase: backend failed to restore, keep session id visible ----
  if (phase === 'resume_error') {
    return (
      <div
        className="h-full flex items-center justify-center bg-surface-subtle dark:bg-dark-surface-subtle"
        data-testid="resume-error-state"
      >
        <div className="w-full max-w-md mx-auto p-6 text-center">
          <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-amber-900 to-amber-600 dark:from-amber-500 dark:to-amber-300 flex items-center justify-center mx-auto mb-3 shadow-notion">
            <AlertCircle className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-semibold text-ink-1">恢复面试失败</h1>
          <p className="text-sm text-ink-3 mt-1">后端暂时连不上,你的面试进度还在,可以重试或返回列表</p>
          {resumeErrorMsg && (
            <div
              data-testid="resume-error-message"
              className="mt-4 p-3 rounded-md bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-sm text-red-600 text-left"
            >
              {resumeErrorMsg}
            </div>
          )}
          <div className="mt-5 space-y-2">
            <Button
              variant="primary"
              size="lg"
              className="w-full"
              onClick={handleRetryResume}
              disabled={resumeRetrying}
              data-testid="resume-retry"
              leftIcon={<Loader2 className={cn('h-4 w-4', resumeRetrying && 'animate-spin')} />}
            >
              重试
            </Button>
            <Link
              to="/interview"
              data-testid="resume-return-list"
              className="block w-full text-center px-4 py-2 rounded-md text-sm text-ink-3 hover:text-ink-1 hover:bg-surface-muted transition-colors"
            >
              返回面试列表
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // ---- setup phase ----
  if (phase === 'setup' || phase === 'connecting') {
    return (
      <div className="h-full flex items-center justify-center bg-surface-subtle dark:bg-dark-surface-subtle">
        <div className="w-full max-w-md mx-auto p-6">
          <div className="text-center mb-6">
            <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-brand-900 to-brand-600 dark:from-brand-500 dark:to-brand-300 flex items-center justify-center mx-auto mb-3 shadow-notion">
              <Sparkles className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-xl font-semibold text-ink-1">开始模拟面试</h1>
            <p className="text-sm text-ink-3 mt-1">AI 将根据你的目标岗位生成结构化面试</p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-ink-1 mb-1.5">
                <Briefcase className="h-3.5 w-3.5 inline mr-1.5" />
                目标岗位
              </label>
              <input
                name="position"
                value={position}
                onChange={(e) => setPosition(e.target.value)}
                placeholder="例如：高级前端工程师"
                className="w-full px-3 py-2 text-sm rounded-md bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border text-ink-1 placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                disabled={phase === 'connecting'}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-ink-1 mb-1.5">
                <Building2 className="h-3.5 w-3.5 inline mr-1.5" />
                目标公司
              </label>
              <input
                name="company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="例如：字节跳动"
                className="w-full px-3 py-2 text-sm rounded-md bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border text-ink-1 placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/30"
                disabled={phase === 'connecting'}
              />
            </div>

            {setupError && (
              <div className="p-3 rounded-md bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-sm text-red-600">
                {setupError}
              </div>
            )}

            <Button
              variant="primary"
              size="lg"
              className="w-full"
              onClick={handleSetup}
              disabled={phase === 'connecting' || !position.trim() || !company.trim()}
              leftIcon={phase === 'connecting' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            >
              {phase === 'connecting' ? '正在创建面试...' : '开始面试'}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // ---- live / completed phase ----
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
              <Avatar name={INTERVIEWER_NAME} size="sm" />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-ink-1 truncate">
                    {INTERVIEWER_NAME}
                  </span>
                  {phase === 'live' && (
                    <>
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-2xs text-emerald-600 dark:text-emerald-400">在线</span>
                    </>
                  )}
                  {phase === 'completed' && (
                    <span className="text-2xs text-ink-3">· 已完成</span>
                  )}
                  {resumedNotice && phase === 'live' && (
                    <span
                      className="text-2xs text-brand-600 dark:text-brand-300 ml-1"
                      data-testid="resumed-notice"
                    >
                      · 已恢复
                    </span>
                  )}
                </div>
                <div className="text-2xs text-ink-3">
                  {company} · {position}
                </div>
              </div>
            </div>

            <div className="flex-1 max-w-md mx-4">
              <ProgressBar
                currentQuestion={Math.min(scores.length, TOTAL_QUESTIONS)}
                totalQuestions={TOTAL_QUESTIONS}
                currentNode={ws.state.currentNode}
              />
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
              {phase === 'live' && (
                <>
                  <Button size="sm" variant="ghost" leftIcon={<Pause className="h-3.5 w-3.5" />}>
                    暂停
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    leftIcon={<Square className="h-3.5 w-3.5" />}
                    onClick={() => setPhase('completed')}
                  >
                    结束
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* 消息流 */}
        <div ref={messagesRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {resumedNotice && phase === 'live' && (
            <div
              data-testid="resume-summary"
              className="max-w-3xl rounded-md border border-brand-200 bg-brand-50/70 px-3 py-2 text-xs text-brand-800 dark:border-brand-500/20 dark:bg-brand-500/10 dark:text-brand-200"
            >
              Restored {userAnswers.length} answers, {questions.length} questions, {scores.length} scores.
            </div>
          )}

          {/* 开场 */}
          <div className="flex gap-3 max-w-3xl">
            <Avatar name={INTERVIEWER_NAME} size="md" />
            <div className="flex-1 min-w-0">
              <div className="text-xs text-ink-3 mb-1.5">{INTERVIEWER_NAME} · 开场</div>
              <div className="inline-block px-4 py-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border text-sm text-ink-1 leading-relaxed shadow-notion-sm">
                你好，我是 AI 面试官。本次面试共 {TOTAL_QUESTIONS} 道题，覆盖技术深度、系统架构、工程实践、沟通协作和算法能力五个维度。请先简单介绍一下你自己，包括你的项目经验和目标岗位。
              </div>
            </div>
          </div>

          {/* 用户回答 + 面试官问题 + 反馈 */}
          {userAnswers.map((ans, idx) => {
            const relatedQuestion = questions[idx] // question generated BEFORE this answer? No...
            // Actually: first answer (idx=0) triggers Q1. Q1 is questions[0].
            // answer idx relates to question idx (the answer to question idx).
            const answerScore = scores.find((s) => s.question_no === ans.seqNo)
            const nextQuestion = questions[idx] // next question after this answer

            return (
              <div key={ans.seqNo}>
                {/* 用户回答 */}
                <div className="flex gap-3 max-w-3xl ml-auto justify-end mb-4">
                  <div className="flex-1 min-w-0 flex flex-col items-end">
                    <div className="text-xs text-ink-3 mb-1.5">
                      你 · 候选人
                    </div>
                    <div className="inline-block px-4 py-3 rounded-lg rounded-tr-sm bg-brand-500 text-white text-sm leading-relaxed max-w-xl">
                      <div data-testid={`restored-answer-${idx}`}>
                        {ans.content}
                      </div>
                    </div>
                  </div>
                  <Avatar name={userDisplayName} size="md" src={userAvatarUrl} />
                </div>

                {/* 反馈卡片 */}
                {answerScore && (
                  <div className="flex gap-3 max-w-3xl mb-4">
                    <Avatar name={INTERVIEWER_NAME} size="md" />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-ink-3 mb-1.5">
                        {INTERVIEWER_NAME} · 评分
                      </div>
                      <div className="p-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border space-y-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              'text-lg font-semibold tabular-nums',
                              answerScore.score >= 8
                                ? 'text-emerald-600'
                                : answerScore.score >= 6
                                  ? 'text-brand-600'
                                  : 'text-amber-600',
                            )}
                          >
                            {answerScore.score}/10
                          </span>
                          <Badge variant="default">{answerScore.dimension}</Badge>
                        </div>
                        <p className="text-sm text-ink-2 leading-relaxed">{answerScore.feedback}</p>
                        {Object.keys(answerScore.sub_scores).length > 0 && (
                          <div className="flex gap-3 text-2xs text-ink-3">
                            {Object.entries(answerScore.sub_scores).map(([k, v]) => (
                              <span key={k}>
                                {k}: <span className="font-medium text-ink-1">{v}</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* 下一道问题 */}
                {nextQuestion && (
                  <div className="flex gap-3 max-w-3xl mb-4">
                    <Avatar name={INTERVIEWER_NAME} size="md" />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-ink-3 mb-1.5">
                        {INTERVIEWER_NAME} · 第 {idx + 1} 题 · {nextQuestion.dimension}
                      </div>
                      <div className="inline-block px-4 py-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border text-sm text-ink-1 leading-relaxed shadow-notion-sm">
                        {nextQuestion.question}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}

          {/* 当前正在流式输出的问题 (when questions.length > userAnswers.length, the latest question is streaming) */}
          {questions.length > userAnswers.length && ws.state.currentNode === 'question_gen' && (
            <div className="flex gap-3 max-w-3xl">
              <Avatar name={INTERVIEWER_NAME} size="md" />
              <div className="flex-1 min-w-0">
                <div className="text-xs text-ink-3 mb-1.5 flex items-center gap-1.5">
                  {INTERVIEWER_NAME} · 第 {questions.length} 题
                  {ws.state.streamingText ? null : (
                    <>
                      <Loader2 className="h-2.5 w-2.5 animate-spin" />
                      <span>正在生成问题</span>
                    </>
                  )}
                </div>
                {ws.state.streamingText ? (
                  <div className="inline-block px-4 py-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border text-sm text-ink-1 leading-relaxed shadow-notion-sm">
                    <StreamingText
                      text={ws.state.streamingText}
                      isStreaming={ws.state.currentNode === 'question_gen'}
                    />
                  </div>
                ) : (
                  <div className="inline-flex items-center gap-1.5 px-4 py-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border">
                    <div className="flex gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="h-1.5 w-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="h-1.5 w-1.5 rounded-full bg-ink-muted animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* AI 评分中 */}
          {aiThinking && ws.state.currentNode !== 'question_gen' && (
            <div className="flex gap-3 max-w-3xl">
              <Avatar name={INTERVIEWER_NAME} size="md" />
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

          {/* 完成报告 */}
          {phase === 'completed' && report && (
            <div className="flex gap-3 max-w-3xl" data-testid="interview-completed-state">
              <Avatar name={INTERVIEWER_NAME} size="md" />
              <div className="flex-1 min-w-0">
                <div className="text-xs text-ink-3 mb-1.5">{INTERVIEWER_NAME} · 面试完成</div>
                <div className="p-4 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="text-3xl font-semibold text-ink-1 tabular-nums">
                      {report.overall_score} <span className="text-base text-ink-3">/ 10</span>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-ink-1">综合评分</div>
                      <div className="text-2xs text-ink-3">满分 10</div>
                    </div>
                    <Badge
                      variant={
                        report.overall_score >= 8.5 ? 'success' : report.overall_score >= 7 ? 'brand' : 'warning'
                      }
                    >
                      {report.overall_score >= 8.5 ? '优秀' : report.overall_score >= 7 ? '良好' : '继续努力'}
                    </Badge>
                  </div>
                  <div className="flex gap-2">
                    <Link to={`/interview/${sessionId}/report`}>
                      <Button variant="primary" size="sm">
                        查看详细报告
                      </Button>
                    </Link>
                    <Link to="/interview">
                      <Button variant="ghost" size="sm">
                        返回列表
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 输入区 */}
        {phase === 'live' && (
          <div className="border-t border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface px-6 py-3 flex-shrink-0">
            {/* 当前维度提示 */}
            {lastQuestion && (
              <div className="mb-2 flex items-center gap-2 text-2xs text-ink-3">
                <Lightbulb className="h-3 w-3 text-amber-500" />
                <span>
                  当前考察维度「{lastQuestion.dimension}」· 第 {currentQuestionIndex}/{TOTAL_QUESTIONS} 题
                </span>
                {lastQuestion.hints.length > 0 && (
                  <span className="text-brand-600 dark:text-brand-300 ml-2">
                    提示：{lastQuestion.hints[0]}
                  </span>
                )}
              </div>
            )}

            {/* WS 错误 */}
            {ws.state.error && (
              <div className="mb-2">
                <ErrorBanner
                  code={ws.state.error.payload?.code || 'internal_error'}
                  message={ws.state.error.payload?.message || ''}
                  retryable={ws.state.error.payload?.retryable}
                  retryCount={ws.state.error.payload?.retry_count}
                  onRetry={() => {
                    if (sessionId && ws.state.lastCheckpointId) {
                      ws.reconnect(sessionId, ws.state.lastCheckpointId)
                    }
                  }}
                />
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
                  data-testid="answer-input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      submitAnswer()
                    }
                  }}
                  placeholder={
                    questions.length === 0
                      ? '介绍你自己，包括目标岗位和项目经验…（Enter 发送）'
                      : '输入你的回答…（Enter 发送，Shift+Enter 换行）'
                  }
                  rows={1}
                  className="w-full px-3 py-2 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:bg-surface dark:focus:bg-dark-surface resize-none max-h-32 transition-all"
                  style={{ minHeight: '36px' }}
                  disabled={aiThinking || ws.state.currentNode === 'report'}
                />
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <Button
                  size="md"
                  variant="primary"
                  leftIcon={<Send className="h-3.5 w-3.5" />}
                  onClick={submitAnswer}
                  disabled={!input.trim() || aiThinking}
                  data-testid="submit-answer"
                >
                  发送
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 右侧实时反馈面板 */}
      <aside className="w-72 border-l border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface flex flex-col flex-shrink-0">
        <div className="px-4 py-3 border-b border-surface-border dark:border-dark-surface-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-brand-500" />
            <span className="text-sm font-semibold text-ink-1">实时反馈</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* 当前评分 */}
          {lastScore ? (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-ink-3">最近评分</div>
                <Badge
                  variant={lastScore.score >= 8 ? 'success' : lastScore.score >= 6 ? 'brand' : 'warning'}
                  leftIcon={<ThumbsUp className="h-2.5 w-2.5" />}
                >
                  {lastScore.score >= 8 ? '优秀' : lastScore.score >= 6 ? '良好' : '加油'}
                </Badge>
              </div>
              <div className="text-center py-3 rounded-md bg-gradient-to-br from-brand-50 to-surface dark:from-brand-500/10 dark:to-dark-surface border border-surface-border dark:border-dark-surface-border">
                <div className="text-3xl font-semibold text-ink-1 tabular-nums">{lastScore.score}</div>
                <div className="text-2xs text-ink-3 mt-0.5">/ 10 分</div>
              </div>
              {lastScore.feedback && (
                <p className="text-2xs text-ink-2 mt-2 leading-relaxed">{lastScore.feedback}</p>
              )}
            </div>
          ) : (
            <div>
              <div className="text-xs text-ink-3 mb-2">等待首轮评分</div>
              <div className="text-center py-3 rounded-md bg-surface-muted dark:bg-dark-surface-muted border border-surface-border dark:border-dark-surface-border">
                <div className="text-2xs text-ink-3">回答第一道题后将显示实时评分</div>
              </div>
            </div>
          )}

          {/* 维度表现 */}
          {dimensionAverages.length > 0 && (
            <div>
              <div className="text-xs text-ink-3 mb-2">维度表现</div>
              <div className="space-y-2">
                {dimensionAverages.map((d) => (
                  <div key={d.name} className="space-y-1">
                    <div className="flex items-center justify-between text-2xs">
                      <span className="text-ink-2">{d.name}</span>
                      <span
                        className={cn(
                          'font-semibold tabular-nums',
                          d.score >= 8
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : d.score >= 6
                              ? 'text-brand-600 dark:text-brand-300'
                              : 'text-amber-600 dark:text-amber-400',
                        )}
                      >
                        {d.score}
                      </span>
                    </div>
                    <Progress
                      value={d.score * 10}
                      size="sm"
                      variant={d.score >= 8 ? 'success' : d.score >= 6 ? 'brand' : 'warning'}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 所有评分记录 */}
          {scores.length > 0 && (
            <div>
              <div className="text-xs text-ink-3 mb-2">答题记录</div>
              <div className="space-y-1.5">
                {scores.map((s, i) => (
                  <div
                    key={s.question_no}
                    className="flex items-center gap-2 p-2 rounded-md bg-surface-muted dark:bg-dark-surface-muted text-2xs"
                  >
                    <span
                      className={cn(
                        'h-5 w-5 rounded text-xs font-semibold flex items-center justify-center flex-shrink-0',
                        s.score >= 8
                          ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700'
                          : s.score >= 6
                            ? 'bg-brand-100 dark:bg-brand-500/20 text-brand-700'
                            : 'bg-amber-100 dark:bg-amber-500/20 text-amber-700',
                      )}
                    >
                      {s.question_no}
                    </span>
                    <span className="flex-1 text-ink-2 truncate">{s.dimension}</span>
                    <span className="font-semibold text-ink-1 tabular-nums">{s.score}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 连接状态 */}
          <div className="pt-2 border-t border-surface-border dark:border-dark-surface-border">
            <div className="flex items-center gap-1.5 text-2xs text-ink-3">
              <span
                className={cn(
                  'h-1.5 w-1.5 rounded-full',
                  ws.state.connected ? 'bg-emerald-500' : ws.state.reconnecting ? 'bg-amber-500' : 'bg-red-500',
                )}
              />
              {ws.state.connected
                ? '已连接'
                : ws.state.reconnecting
                  ? `重连中 (${ws.state.reconnectAttempt}/5)`
                  : '未连接'}
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}

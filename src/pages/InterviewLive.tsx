import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom'
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
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Progress } from '@/components/ui/Progress'
import { Avatar } from '@/components/ui/Avatar'
import { useAvatarBlob } from '@/hooks/queries/useAvatarBlob'
import { cn } from '@/lib/utils'
import { zhCN } from '@/lib/i18n/zh-CN'
import { useInterviewWS, type WSEvent } from '@/hooks/useInterviewWS'
import { useAuthStore } from '@/stores/useAuthStore'
import { interviewSessionRepo, resolvePlanStatus, type InterviewSession, type PlanStatus } from '@/repositories/interviewSessionRepo'
import { getAccessToken } from '@/api/token-storage'
import { ErrorBanner } from '@/components/interview/ErrorBanner'
import { InterviewPlanPanel } from '@/components/interview/InterviewPlanPanel'
import { DoubaoCardWorkspace } from '@/components/interview/DoubaoCardWorkspace'
import { StreamingText } from '@/components/interview/StreamingText'
import { ProgressBar } from '@/components/interview/ProgressBar'
import type { InterviewPlan, InterviewWebResearch } from '@/repositories/interviewSessionRepo'

const TOTAL_QUESTIONS = 5
const INTERVIEWER_NAME = 'AI 面试官'

// REQ-048 US3 T071 — effective_max drives the progress bar so the user
// sees a meaningful 「第 X/Y 题」 counter for the 10-15 question envelope.
// When the backend exposes the session's effective_max, prefer that;
// otherwise fall back to TOTAL_QUESTIONS (legacy 5-round mode) so the
// quick-drill path keeps its existing counter behaviour.
function resolveEffectiveMax(state: {
  effectiveMax?: number | null
  maxQuestions?: number | null
  mode?: string | null
}): number {
  if (typeof state.effectiveMax === 'number' && state.effectiveMax >= 7 && state.effectiveMax <= 15) {
    return state.effectiveMax
  }
  if (state.mode === 'full' && typeof state.maxQuestions === 'number') {
    return state.maxQuestions
  }
  return TOTAL_QUESTIONS
}

function isInterviewWsMockMode(): boolean {
  const override = (globalThis as any).__VITE_USE_MOCK_OVERRIDE__
  if (typeof override === 'string') return override === 'true'
  return (import.meta as any).env?.VITE_USE_MOCK === 'true'
}

interface QuestionData {
  question_no?: number
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

/** Shape of a question entry returned by the resume API. */
interface RestoredQuestionEntry {
  question_no?: number | null
  sequence_no?: number | null
  question?: string | null
  dimension?: string | null
  expected_points?: string[] | null
  hints?: string[] | null
}

/** Shape of a score entry returned by the resume API. */
interface RestoredScoreEntry {
  question_no?: number | null
  sequence_no?: number | null
  score?: number | null
  dimension?: string | null
  feedback?: string | null
  sub_scores?: Record<string, number> | null
}

/** Shape of a message entry returned by the resume API. */
interface RestoredMessageEntry {
  role?: string | null
  type?: string | null
  content?: string | null
}

interface RestoredNumberedEntry {
  question_no?: number | null
  sequence_no?: number | null
}

// ── Runtime-safe resume-data validators ────────────────────────────

/** Narrow unknown to Record<string, unknown> (object & not null & not array). */
function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v)
}

/** Return a positive integer, or null. Rejects 0, negative, NaN, fractional. */
function toPositiveIntOrNull(v: unknown): number | null {
  if (typeof v === 'number' && Number.isInteger(v) && v > 0) return v
  if (typeof v === 'string') {
    const n = Number(v)
    if (Number.isInteger(n) && n > 0) return n
  }
  return null
}

/** Return a nullable string. */
function toNullableString(v: unknown): string | null {
  return typeof v === 'string' ? v : null
}

/** Resolve the single identity used by both question and score recovery. */
function effectiveQuestionNumber(entry: RestoredNumberedEntry): number | null {
  return entry.question_no ?? entry.sequence_no ?? null
}

/** Filter unknown to a string array; fails safely to []. */
function toStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((item): item is string => typeof item === 'string') : []
}

/** Safely construct a RestoredQuestionEntry from an unknown record. */
function toRestoredQuestion(raw: Record<string, unknown>): RestoredQuestionEntry {
  return {
    question_no: toPositiveIntOrNull(raw.question_no),
    sequence_no: toPositiveIntOrNull(raw.sequence_no),
    question: toNullableString(raw.question),
    dimension: toNullableString(raw.dimension),
    expected_points: toStringArray(raw.expected_points),
    hints: toStringArray(raw.hints),
  }
}

/** Safely construct a RestoredScoreEntry from an unknown record. */
function toRestoredScore(raw: Record<string, unknown>): RestoredScoreEntry {
  let subScores: Record<string, number> | null = null
  const rawSub: unknown = raw.sub_scores
  if (isRecord(rawSub)) {
    subScores = {}
    for (const [k, v] of Object.entries(rawSub)) {
      if (typeof v === 'number' && !Number.isNaN(v)) {
        subScores[k] = v
      }
    }
    if (Object.keys(subScores).length === 0) subScores = null
  }
  return {
    question_no: toPositiveIntOrNull(raw.question_no),
    sequence_no: toPositiveIntOrNull(raw.sequence_no),
    score: typeof raw.score === 'number' && !Number.isNaN(raw.score) ? raw.score : null,
    dimension: toNullableString(raw.dimension),
    feedback: toNullableString(raw.feedback),
    sub_scores: subScores,
  }
}

/** Safely construct a RestoredMessageEntry from an unknown record. */
function toRestoredMessage(raw: Record<string, unknown>): RestoredMessageEntry {
  return {
    role: toNullableString(raw.role),
    type: toNullableString(raw.type),
    content: toNullableString(raw.content),
  }
}

function uniqueBy<T>(items: T[], keyOf: (item: T, index: number) => string): T[] {
  const seen = new Set<string>()
  return items.filter((item, index) => {
    const key = keyOf(item, index)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export default function InterviewLive() {
  const token = getAccessToken()
  const { id: routeSessionId } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const currentUser = useAuthStore((s) => s.user)
  const userAvatarUrl = useAvatarBlob(currentUser?.avatar_url ?? null) ?? undefined
  const userDisplayName =
    currentUser?.display_name || currentUser?.email.split('@')[0] || 'You'

  // ---- phase state ----
  const [phase, setPhase] = useState<
    'setup' | 'connecting' | 'live' | 'completed' | 'resume_error' | 'doubao_card'
  >(routeSessionId ? 'connecting' : 'setup')
  const [position, setPosition] = useState('')
  const [company, setCompany] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(routeSessionId || null)
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
  const [interviewPlan, setInterviewPlan] = useState<InterviewPlan | null>(null)
  const [webResearch, setWebResearch] = useState<InterviewWebResearch | null>(null)
  const [planOpen, setPlanOpen] = useState(false)
  // REQ-048 US3 T071 — session metadata that drives the progress bar.
  const [sessionMode, setSessionMode] = useState<string | null>(null)
  const [sessionMaxQuestions, setSessionMaxQuestions] = useState<number | null>(null)
  const [sessionEffectiveMax, setSessionEffectiveMax] = useState<number | null>(null)
  // REQ-058 — plan lifecycle visibility
  const [planStatus, setPlanStatus] = useState<PlanStatus>('pending')
  const [planErrorMessage, setPlanErrorMessage] = useState<string | null>(null)
  const [planDegraded, setPlanDegraded] = useState(false)
  const [degradeConfirming, setDegradeConfirming] = useState(false)
  // REQ-061 US4 — server-derived controls / recovery chrome
  const [availableActions, setAvailableActions] = useState<string[]>([])
  const [savedRoundExplanation, setSavedRoundExplanation] = useState<string | null>(null)
  const [reportFailure, setReportFailure] = useState<{ code: string; message: string } | null>(null)
  const [pointsSummary, setPointsSummary] = useState<InterviewSession['points_summary']>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [pauseBusy, setPauseBusy] = useState(false)

  // track user answers locally
  const [userAnswers, setUserAnswers] = useState<Array<{ content: string; seqNo: number }>>([])

  const messagesRef = useRef<HTMLDivElement>(null)

  // ---- WebSocket ----
  const ws = useInterviewWS(token || '')

  const syncPlannerOutputs = useCallback(async (id: string) => {
    const sess = await interviewSessionRepo.getById(id)
    setInterviewPlan(sess.interview_plan ?? null)
    setWebResearch(sess.web_research ?? null)
    setSessionMode(sess.mode ?? null)
    setSessionMaxQuestions(sess.max_questions ?? null)
    setSessionEffectiveMax(sess.effective_max ?? null)
    setPlanStatus(resolvePlanStatus(sess))
    setPlanErrorMessage(sess.plan_error_message ?? null)
    setPlanDegraded(Boolean(sess.degraded))
    if (sess.available_actions) setAvailableActions(sess.available_actions)
    if (sess.points_summary) setPointsSummary(sess.points_summary)
    if (sess.task_id) setTaskId(sess.task_id)
    if (sess.failure) {
      setReportFailure({ code: sess.failure.code, message: sess.failure.message })
    }
    if (sess.status === 'partially_succeeded' && sess.failure) {
      // Keep live phase so failure chrome is visible without claiming completion.
      setPhase((p) => (p === 'completed' ? 'live' : p))
    }
    ws.hydrateRuntime?.({
      taskId: sess.task_id ?? null,
      executionId: sess.execution_id ?? null,
      availableActions: sess.available_actions ?? [],
      pointsSummary: sess.points_summary ?? null,
    })
    if (sess.interview_plan) setPlanOpen((open) => open || questions.length === 0)
    return sess
  }, [questions.length, ws])

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
    const applyScore = (summary: Record<string, any>) => {
      if (!(summary.score > 0)) return
      const qNo = Number(summary.question_no || 0)
      setScores((prev) => {
        if (qNo > 0 && prev.some((s) => Number(s.question_no) === qNo)) return prev
        return [...prev, {
          question_no: qNo,
          score: summary.score,
          dimension: summary.dimension || '',
          feedback: summary.feedback || '',
          sub_scores: summary.sub_scores || {},
        }]
      })
    }

    switch (evt.type) {
      case 'round.score':
      case 'score.delivered': {
        applyScore(evt.payload.summary || evt.payload)
        break
      }
      case 'round.next_question': {
        const q = evt.payload
        if (q.question) {
          setQuestions((prev) => {
            const questionNo = Number(q.question_no || 0)
            const exists = questionNo > 0
              ? prev.some((item) => item.question_no === questionNo)
              : prev.some((item) => item.question === q.question)
            if (exists) return prev
            return [...prev, {
              question_no: questionNo > 0 ? questionNo : undefined,
              question: q.question,
              dimension: q.dimension || '',
              expected_points: q.expected_points || [],
              hints: q.hints || [],
            }]
          })
        }
        break
      }
      case 'node.completed': {
        const summary = evt.payload.summary || {}
        if (evt.node_name === 'score' && summary.score > 0) {
          applyScore(summary)
        }
        if (evt.node_name === 'question_gen' && summary.question) {
          const questionNo = Number(summary.question_no || 0)
          setQuestions((prev) => {
            const exists = questionNo > 0
              ? prev.some((q) => q.question_no === questionNo)
              : prev.some((q) => q.question === summary.question)
            if (exists) return prev
            return [...prev, {
              question_no: questionNo > 0 ? questionNo : undefined,
              question: summary.question,
              dimension: summary.dimension || '',
              expected_points: summary.expected_points || [],
              hints: summary.hints || [],
            }]
          })
        }
        if (evt.node_name === 'report') {
          if (summary.failed || summary.error_code) {
            setReportFailure({
              code: summary.error_code || 'REPORT_ASSEMBLY_FAILED',
              message: summary.message || summary.feedback || '报告生成失败，已完成评分已保留。',
            })
          } else {
            setReport({
              overall_score: summary.overall_score || 0,
              report_id: summary.report_id || '',
            })
            setPhase('completed')
          }
        }
        break
      }
      case 'error': {
        setAiThinking(false)
        if (evt.payload?.code || evt.payload?.message) {
          setReportFailure({
            code: String(evt.payload.code || 'REPORT_ASSEMBLY_FAILED'),
            message: String(evt.payload.message || '报告生成失败，已完成评分已保留。'),
          })
        }
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
    const el = messagesRef.current
    if (!el) return
    if (typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    } else {
      el.scrollTop = el.scrollHeight
    }
  }, [questions, scores, ws.state.streamingText, userAnswers, aiThinking, ws.state.turnPhase])

  // ---- resume: when /interview/:id/live, restore state and connect WS ----
  const resumeRanRef = useRef(false)
  useEffect(() => {
    if (!routeSessionId || resumeRanRef.current) return
    resumeRanRef.current = true

    const restore = async () => {
      try {
        const sess = await syncPlannerOutputs(routeSessionId)
        if (sess.status === 'completed') {
          // Already finished — go straight to report view
          setPosition(sess.position || '')
          setCompany(sess.company || '')
          setSessionId(routeSessionId)
          setPhase('completed')
          setReport({ overall_score: Number(sess.overall_score || 0), report_id: '' })
          return
        }

        if (sess.mode === 'doubao') {
          setPosition(sess.position || '')
          setCompany(sess.company || '')
          setSessionId(routeSessionId)
          if (!sess.interview_plan) {
            await interviewSessionRepo.generatePlan(routeSessionId)
            await syncPlannerOutputs(routeSessionId)
          }
          setPhase('doubao_card')
          return
        }

        if (isInterviewWsMockMode()) {
          setPosition(sess.position || '')
          setCompany(sess.company || '')
          setSessionId(routeSessionId)
          setResumedNotice(true)
          ws.connect()
          setPhase('live')
          return
        }

        const resumed = await interviewSessionRepo.resume(routeSessionId)
        const values = resumed.data?.values || {}

        // ── Safely validate resume collections ──
        // Treat each collection as unknown at the boundary, require
        // Array.isArray, filter record entries, and fail-safe to [].

        const rawQuestions: unknown = values.questions
        const restoredQuestions: RestoredQuestionEntry[] = Array.isArray(rawQuestions)
          ? rawQuestions.filter(isRecord).map(toRestoredQuestion)
          : []

        const rawScores: unknown = values.scores
        const restoredScores: RestoredScoreEntry[] = Array.isArray(rawScores)
          ? rawScores.filter(isRecord).map(toRestoredScore)
          : []

        const rawMessages: unknown = values.messages
        const restoredMessages: RestoredMessageEntry[] = Array.isArray(rawMessages)
          ? rawMessages.filter(isRecord).map(toRestoredMessage)
          : []

        const userMessages = restoredMessages
          .filter((m) => m.role === 'user' || m.type === 'human')
          .map((m) => (m.content ?? ''))

        setPosition(sess.position || '')
        setCompany(sess.company || '')
        setInterviewPlan(sess.interview_plan ?? values.interview_plan ?? null)
        setWebResearch(sess.web_research ?? values.web_research ?? null)

        setQuestions((prev) => {
          // question_no and sequence_no describe the same effective identity.
          const questionKey = (q: RestoredQuestionEntry, idx: number): string => {
            const questionNo = effectiveQuestionNumber(q)
            if (questionNo != null) return `question-${questionNo}`
            return q.question ? `txt-${q.question}` : `fallback-${idx}`
          }
          const restored = uniqueBy(
            restoredQuestions,
            questionKey,
          ).map((q: RestoredQuestionEntry): QuestionData => ({
            // Valid positive question_no is authoritative; fall back to
            // sequence_no (also validated positive int).  Never default
            // missing/null to 0.
            question_no: effectiveQuestionNumber(q) ?? undefined,
            question: q.question ?? '',
            dimension: q.dimension ?? '',
            expected_points: q.expected_points ?? [],
            hints: q.hints ?? [],
          }))
          // Merge WS events already applied before resume resolved (avoid wipe).
          const merged = [...restored]
          for (const q of prev) {
            const exists = merged.some((item) => {
              if (q.question_no != null && Number.isInteger(q.question_no) && q.question_no > 0 &&
                  item.question_no != null) {
                return item.question_no === q.question_no
              }
              return item.question === q.question
            })
            if (!exists) merged.push(q)
          }
          return merged
        })

        setScores((prev) => {
          const scoreKey = (s: RestoredScoreEntry, idx: number): string => {
            const questionNo = effectiveQuestionNumber(s)
            return questionNo != null ? `score-${questionNo}` : `fallback-${idx}`
          }
          const restored = uniqueBy(
            restoredScores,
            scoreKey,
          ).map((s: RestoredScoreEntry): ScoreData => ({
            question_no: effectiveQuestionNumber(s) ?? 0,
            score: s.score ?? 0,
            dimension: s.dimension ?? '',
            feedback: s.feedback ?? '',
            sub_scores: s.sub_scores ?? {},
          }))
          const merged = [...restored]
          for (const s of prev) {
            if (s.question_no > 0 && merged.some((item) => item.question_no === s.question_no)) continue
            merged.push(s)
          }
          return merged
        })

        // seqNo is 0-based WS sequence; question_no from scores is 1-based.
        // Map answer i → score.question_no === i (intro at 0 has no score).
        const reconstructedAnswers = userMessages.map((content, idx) => ({
          content,
          seqNo: idx,
        }))
        setUserAnswers(reconstructedAnswers)
        setSequenceNo(reconstructedAnswers.length)

        if (sess.duration_sec) setElapsed(sess.duration_sec)

        setSessionId(routeSessionId)
        setResumedNotice(true)
        if (Array.isArray(resumed.data?.available_actions)) {
          setAvailableActions(resumed.data.available_actions)
        } else if (sess.available_actions) {
          setAvailableActions(sess.available_actions)
        }
        if (resumed.data?.task_id || sess.task_id) {
          setTaskId(String(resumed.data?.task_id ?? sess.task_id))
        }
        ws.hydrateRuntime?.({
          taskId: resumed.data?.task_id
            ? String(resumed.data.task_id)
            : sess.task_id ?? null,
          executionId: resumed.data?.execution_id
            ? String(resumed.data.execution_id)
            : sess.execution_id ?? null,
          availableActions:
            resumed.data?.available_actions ?? sess.available_actions ?? [],
          pointsSummary: sess.points_summary ?? null,
        })
        if (typeof resumed.data?.saved_round_explanation === 'string') {
          setSavedRoundExplanation(resumed.data.saved_round_explanation)
        }
        if (sess.failure) {
          setReportFailure({ code: sess.failure.code, message: sess.failure.message })
        }
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

  const planFetchAttemptedRef = useRef(false)
  useEffect(() => {
    if (!sessionId || interviewPlan || !ws.state.lastCheckpointId || planFetchAttemptedRef.current) return
    planFetchAttemptedRef.current = true
    syncPlannerOutputs(sessionId).catch((err) => {
      planFetchAttemptedRef.current = false
      console.warn('[interview-live] planner output sync failed', err)
    })
  }, [interviewPlan, sessionId, syncPlannerOutputs, ws.state.lastCheckpointId])

  const planPollRef = useRef(false)
  useEffect(() => {
    if (!sessionId || planStatus !== 'pending' || planPollRef.current) return
    planPollRef.current = true
    let cancelled = false

    const poll = async () => {
      const deadline = Date.now() + 90_000
      while (!cancelled && Date.now() < deadline) {
        try {
          const sess = await interviewSessionRepo.getById(sessionId)
          if (cancelled) return
          const status = resolvePlanStatus(sess)
          setPlanStatus(status)
          setPlanErrorMessage(sess.plan_error_message ?? null)
          setPlanDegraded(Boolean(sess.degraded))
          if (sess.interview_plan) {
            setInterviewPlan(sess.interview_plan)
            setWebResearch(sess.web_research ?? null)
          }
          if (status !== 'pending') return
        } catch (err) {
          console.warn('[interview-live] plan status poll failed', err)
          return
        }
        await new Promise((resolve) => setTimeout(resolve, 1_500))
      }
    }

    void poll()
    return () => {
      cancelled = true
    }
  }, [planStatus, sessionId])

  const handleConfirmDegrade = useCallback(async () => {
    if (!sessionId || degradeConfirming) return
    setDegradeConfirming(true)
    try {
      const result = await interviewSessionRepo.confirmPlanDegrade(sessionId)
      const sess = result.data
      setPlanStatus(resolvePlanStatus(sess))
      setPlanDegraded(Boolean(sess.degraded))
      setPlanErrorMessage(sess.plan_error_message ?? null)
    } catch (err: any) {
      setPlanErrorMessage(err?.message || '降级确认失败，请稍后重试。')
    } finally {
      setDegradeConfirming(false)
    }
  }, [degradeConfirming, sessionId])

  const effectiveActions =
    availableActions.length > 0
      ? availableActions
      : (ws.state.availableActions ?? [])

  const handlePauseInterview = useCallback(async () => {
    if (!sessionId || pauseBusy) return
    setPauseBusy(true)
    try {
      const result = await interviewSessionRepo.pause(sessionId)
      if (result.available_actions) setAvailableActions(result.available_actions)
      if (result.task_id) setTaskId(result.task_id)
      if (result.points_summary) setPointsSummary(result.points_summary)
      ws.pause?.(sessionId)
    } catch (err) {
      console.warn('[interview-live] pause failed', err)
    } finally {
      setPauseBusy(false)
    }
  }, [pauseBusy, sessionId, ws])

  const handleResumeInterview = useCallback(async () => {
    if (!sessionId || pauseBusy) return
    setPauseBusy(true)
    try {
      const result = await interviewSessionRepo.resumeFromPause(sessionId)
      if (result.available_actions) setAvailableActions(result.available_actions)
      if (result.task_id) setTaskId(result.task_id)
      if (result.points_summary) setPointsSummary(result.points_summary)
      ws.resume?.(sessionId)
    } catch (err) {
      console.warn('[interview-live] resume-from-pause failed', err)
    } finally {
      setPauseBusy(false)
    }
  }, [pauseBusy, sessionId, ws])

  const handleActiveEnd = useCallback(async () => {
    if (!sessionId) return
    try {
      const result = await interviewSessionRepo.activeEnd(sessionId, {
        confirm_partial_report: true,
      })
      if (result.available_actions) setAvailableActions(result.available_actions)
      if (result.points_summary) setPointsSummary(result.points_summary)
      if (result.status === 'partially_succeeded') {
        setReportFailure((prev) =>
          prev ?? {
            code: 'PARTIAL_END',
            message: '面试已结束；部分报告里程碑可能仍在恢复中。',
          },
        )
      } else {
        setPhase('completed')
      }
    } catch (err) {
      console.warn('[interview-live] active-end failed', err)
      setPhase('completed')
    }
  }, [sessionId])

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

  // clear aiThinking when score arrives or question starts streaming
  useEffect(() => {
    if (ws.state.turnPhase === 'awaiting_question' || ws.state.turnPhase === 'generating_question') {
      setAiThinking(false)
    }
    if (ws.state.currentNode === 'question_gen' && ws.state.streamingText) {
      setAiThinking(false)
    }
  }, [ws.state.currentNode, ws.state.streamingText, ws.state.turnPhase])

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
  const turnPhase = ws.state.turnPhase
  const isPlanBlocking = planStatus === 'failed' && !planDegraded
  const isInputLocked =
    isPlanBlocking ||
    turnPhase !== 'idle' ||
    ws.state.currentNode === 'report'
  const inputStatusCopy =
    turnPhase === 'scoring'
      ? '面试官正在评估你的回答…'
      : turnPhase === 'awaiting_question'
        ? '正在出下一题…'
        : turnPhase === 'generating_question'
          ? '正在生成下一题…'
          : null
  const latestAnswer = userAnswers.length > 0 ? userAnswers[userAnswers.length - 1] : null
  const latestScore =
    latestAnswer != null
      ? scores.find((s) => s.question_no === latestAnswer.seqNo) ?? null
      : null
  const showScoreFirstPending =
    turnPhase === 'awaiting_question' &&
    scores.length > 0 &&
    questions.length <= Math.max(userAnswers.length, scores.length)

  const pendingScore = scores[scores.length - 1] ?? null

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

  if (!routeSessionId && phase === 'setup') {
    const search = searchParams.toString()
    return (
      <Navigate
        to={{
          pathname: '/interview/mode',
          search: search ? `?${search}` : '',
        }}
        replace
      />
    )
  }

  if (phase === 'connecting') {
    return (
      <div className="flex h-full items-center justify-center bg-surface-subtle p-6 dark:bg-dark-surface-subtle">
        <div className="flex items-center gap-2 rounded-md border border-line-2 bg-bg-1 px-4 py-3 text-sm text-ink-3 shadow-sm">
          <Loader2 className="h-4 w-4 animate-spin" />
          正在恢复面试会话
        </div>
      </div>
    )
  }

  if (phase === 'doubao_card' && sessionId) {
    return (
      <div
        className="fixed inset-0 z-50 overflow-y-auto bg-surface-subtle px-2 py-3 sm:px-6 sm:py-5 dark:bg-dark-surface-subtle"
        data-testid="doubao-card-page"
      >
        <div className="mx-auto flex max-w-[560px] flex-col gap-3">
          <div className="flex items-center justify-between gap-3 px-1">
            <div>
              <h1 className="text-lg font-semibold text-ink-1">豆包 Prompt</h1>
              <p className="mt-0.5 text-xs text-ink-3">
                {company} · {position}
              </p>
            </div>
            <Link to="/interview">
              <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-3.5 w-3.5" />}>
                返回列表
              </Button>
            </Link>
          </div>
          <DoubaoCardWorkspace sessionId={sessionId} />
        </div>
      </div>
    )
  }

  // ---- live / completed phase ----
  const effectiveQuestionTotal = resolveEffectiveMax({
    effectiveMax: sessionEffectiveMax,
    maxQuestions: sessionMaxQuestions,
    mode: sessionMode,
  })

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
                currentQuestion={Math.min(
                  scores.length,
                  effectiveQuestionTotal,
                )}
                totalQuestions={effectiveQuestionTotal}
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
                  {effectiveActions.includes('pause') && (
                    <Button
                      size="sm"
                      variant="ghost"
                      leftIcon={<Pause className="h-3.5 w-3.5" />}
                      onClick={() => void handlePauseInterview()}
                      disabled={pauseBusy}
                      data-testid="interview-action-pause"
                    >
                      暂停
                    </Button>
                  )}
                  {effectiveActions.includes('resume') && (
                    <Button
                      size="sm"
                      variant="ghost"
                      leftIcon={<Pause className="h-3.5 w-3.5" />}
                      onClick={() => void handleResumeInterview()}
                      disabled={pauseBusy}
                      data-testid="interview-action-resume"
                    >
                      继续
                    </Button>
                  )}
                  {(effectiveActions.includes('end') || effectiveActions.includes('cancel') || effectiveActions.length === 0) && (
                    <Button
                      size="sm"
                      variant="danger"
                      leftIcon={<Square className="h-3.5 w-3.5" />}
                      onClick={() => void handleActiveEnd()}
                      data-testid="interview-action-end"
                    >
                      结束
                    </Button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* 消息流 */}
        <div ref={messagesRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {(planStatus === 'pending' || planStatus === 'ready' || planStatus === 'failed' || planStatus === 'degraded') && (
            <PlanPhaseBanner
              status={planStatus}
              errorMessage={planErrorMessage}
              degraded={planDegraded}
              onConfirmDegrade={handleConfirmDegrade}
              confirming={degradeConfirming}
            />
          )}

          {interviewPlan && (
            <div className="max-w-3xl">
              <InterviewPlanPanel
                plan={interviewPlan}
                webResearch={webResearch}
                open={planOpen}
                onToggle={() => setPlanOpen((open) => !open)}
                compact
              />
            </div>
          )}

          {resumedNotice && phase === 'live' && (
            <div
              data-testid="resume-summary"
              className="max-w-3xl rounded-lg border border-brand-200 bg-brand-50/60 px-4 py-3 text-sm text-brand-800"
            >
              已从断点恢复面试会话
              {taskId ? (
                <>
                  {' · '}
                  <Link to={`/ai-tasks/${encodeURIComponent(taskId)}`} className="underline">
                    查看 AI 任务
                  </Link>
                </>
              ) : null}
              {pointsSummary ? (
                <span className="ml-2 text-xs text-ink-3">
                  点数 已扣 {pointsSummary.settled ?? 0} / 预留 {pointsSummary.reserved ?? 0}
                </span>
              ) : null}
            </div>
          )}

          {savedRoundExplanation && (
            <div
              data-testid="saved-round-explanation"
              className="max-w-3xl rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
            >
              {savedRoundExplanation}
            </div>
          )}

          {reportFailure && (
            <div
              data-testid="interview-report-failure"
              className="max-w-3xl rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950"
              role="alert"
            >
              <p className="font-medium">{reportFailure.message}</p>
              <p className="mt-1 text-xs text-amber-800">
                错误码 {reportFailure.code}
                {taskId ? (
                  <>
                    {' · '}
                    <Link to={`/ai-tasks/${encodeURIComponent(taskId)}`} className="underline">
                      任务详情
                    </Link>
                  </>
                ) : null}
                {pointsSummary ? (
                  <> · 已结算 {pointsSummary.settled ?? 0} 点</>
                ) : null}
              </p>
            </div>
          )}

          {/* 开场 */}
          <div className="flex gap-3 max-w-3xl">
            <Avatar name={INTERVIEWER_NAME} size="md" />
            <div className="flex-1 min-w-0">
              <div className="text-xs text-ink-3 mb-1.5">{INTERVIEWER_NAME} · 开场</div>
              <div className="inline-block px-4 py-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border text-sm text-ink-1 leading-relaxed shadow-notion-sm">
                你好，我是 AI 面试官。本次面试共 {effectiveQuestionTotal} 道题，覆盖技术深度、系统架构、工程实践、沟通协作和算法能力五个维度。请先简单介绍一下你自己，包括你的项目经验和目标岗位。
              </div>
            </div>
          </div>

          {/* 用户回答 + 面试官问题 + 反馈 */}
          {userAnswers.map((ans, idx) => {
            const relatedQuestion = questions[idx] // question generated BEFORE this answer? No...
            // Actually: first answer (idx=0) triggers Q1. Q1 is questions[0].
            // answer idx relates to question idx (the answer to question idx).
            // Scores use 1-based question_no; first user turn (seqNo=0) is intro (no score).
            const answerScore = scores.find((s) => Number(s.question_no) === ans.seqNo)
            const nextQuestion = questions[idx] // next question after this answer
            // score-first panel owns the pending score until next question arrives
            const hideInThread =
              showScoreFirstPending &&
              pendingScore != null &&
              Number(answerScore?.question_no) === Number(pendingScore.question_no)

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
                {answerScore && !hideInThread && (
                  <div className="flex gap-3 max-w-3xl mb-4" data-testid="answer-score-card">
                    <Avatar name={INTERVIEWER_NAME} size="md" />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-ink-3 mb-1.5">
                        {INTERVIEWER_NAME} · 评分
                      </div>
                      <div className="p-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border space-y-2">
                        <div className="flex items-center gap-2">
                          <Badge variant="default">{answerScore.dimension}</Badge>
                        </div>
                        <p className="text-sm text-ink-2 leading-relaxed">
                          <span
                            className={cn(
                              'font-semibold tabular-nums',
                              answerScore.score >= 8
                                ? 'text-emerald-600'
                                : answerScore.score >= 6
                                  ? 'text-brand-600'
                                  : 'text-amber-600',
                            )}
                          >
                            {answerScore.score}/10
                          </span>
                          {' · '}
                          {answerScore.feedback}
                        </p>
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

          {/* REQ-058 — score visible in thread; show next-question wait hint */}
          {showScoreFirstPending && (
            <div className="flex gap-3 max-w-3xl" data-testid="score-first-pending">
              <Avatar name={INTERVIEWER_NAME} size="md" />
              <div className="flex-1 min-w-0 space-y-2">
                {pendingScore && (
                  <div
                    className="p-3 rounded-lg rounded-tl-sm bg-surface dark:bg-dark-surface border border-surface-border dark:border-dark-surface-border"
                    data-testid="score-first-score"
                  >
                    <p className="text-sm text-ink-2 leading-relaxed">
                      <span className="font-semibold text-emerald-600 tabular-nums">
                        {pendingScore.score}/10
                      </span>
                      {' · '}
                      {pendingScore.feedback}
                    </p>
                  </div>
                )}
                <div className="text-xs text-ink-3 mb-1.5 flex items-center gap-1.5">
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                  正在出下一题
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

          {/* 当前正在流式输出的问题 (when questions.length > userAnswers.length, the latest question is streaming) */}
          {questions.length > userAnswers.length && ws.state.currentNode === 'question_gen' && !showScoreFirstPending && (
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

          {/* AI 评分中 / 生成下一题 */}
          {turnPhase === 'scoring' && (
            <div className="flex gap-3 max-w-3xl" data-testid="turn-phase-scoring">
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

          {turnPhase === 'generating_question' && questions.length <= userAnswers.length && !showScoreFirstPending && (
            <div className="flex gap-3 max-w-3xl" data-testid="turn-phase-generating">
              <Avatar name={INTERVIEWER_NAME} size="md" />
              <div className="flex-1 min-w-0">
                <div className="text-xs text-ink-3 mb-1.5 flex items-center gap-1.5">
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                  正在出下一题
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

          {/* legacy aiThinking fallback when turnPhase not yet updated */}
          {aiThinking && turnPhase === 'idle' && ws.state.currentNode !== 'question_gen' && (
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
                  当前考察维度「{lastQuestion.dimension}」· 第 {currentQuestionIndex}/{resolveEffectiveMax({
                    effectiveMax: sessionEffectiveMax,
                    maxQuestions: sessionMaxQuestions,
                    mode: sessionMode,
                  })} 题
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
                    isPlanBlocking
                      ? '面试计划生成失败，请先确认是否降级继续…'
                      : inputStatusCopy
                        ? inputStatusCopy
                        : questions.length === 0
                          ? '介绍你自己，包括目标岗位和项目经验…（Enter 发送）'
                          : '输入你的回答…（Enter 发送，Shift+Enter 换行）'
                  }
                  rows={1}
                  className="w-full px-3 py-2 text-sm rounded-md bg-surface-muted dark:bg-dark-surface-muted text-ink-1 placeholder:text-ink-muted border-0 focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:bg-surface dark:focus:bg-dark-surface resize-none max-h-32 transition-all"
                  style={{ minHeight: '36px' }}
                  disabled={isInputLocked}
                />
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <Button
                  size="md"
                  variant="primary"
                  leftIcon={<Send className="h-3.5 w-3.5" />}
                  onClick={submitAnswer}
                  disabled={!input.trim() || isInputLocked}
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
                    key={s.question_no > 0 ? `question-${s.question_no}` : `unidentified-${i}`}
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

function PlanPhaseBanner({
  status,
  errorMessage,
  degraded,
  onConfirmDegrade,
  confirming,
}: {
  status: PlanStatus
  errorMessage: string | null
  degraded: boolean
  onConfirmDegrade: () => void
  confirming: boolean
}) {
  if (status === 'ready') {
    return (
      <div
        data-testid="plan-phase-banner-ready"
        className="max-w-3xl rounded-md border border-emerald-200 bg-emerald-50/70 px-3 py-2 text-xs text-emerald-800 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200"
      >
        <span className="inline-flex items-center gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5" />
          面试计划已就绪，将按 JD 侧重点出题
        </span>
      </div>
    )
  }

  if (status === 'pending') {
    return (
      <div
        data-testid="plan-phase-banner-pending"
        className="max-w-3xl rounded-md border border-brand-200 bg-brand-50/70 px-3 py-2 text-xs text-brand-800 dark:border-brand-500/20 dark:bg-brand-500/10 dark:text-brand-200"
      >
        <span className="inline-flex items-center gap-1.5">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          正在生成面试计划，请稍候…
        </span>
      </div>
    )
  }

  if (status === 'degraded' || degraded) {
    return (
      <div
        data-testid="plan-phase-banner-degraded"
        className="max-w-3xl rounded-md border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-100"
      >
        <span className="inline-flex items-center gap-1.5">
          <AlertCircle className="h-3.5 w-3.5" />
          已降级为通用题模式，评分与报告仍可用
        </span>
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div
        data-testid="plan-phase-banner-failed"
        className="max-w-3xl rounded-md border border-red-200 bg-red-50/80 px-3 py-3 text-sm text-red-800 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-100 space-y-2"
      >
        <div className="flex items-start gap-2">
          <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-medium">面试计划生成失败</div>
            <p className="mt-1 text-xs leading-relaxed">
              {errorMessage || '暂时无法根据 JD 生成定制计划，请稍后重试或选择降级继续。'}
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="secondary"
          loading={confirming}
          onClick={onConfirmDegrade}
          data-testid="plan-degrade-confirm"
        >
          确认降级，继续通用题面试
        </Button>
      </div>
    )
  }

  return null
}

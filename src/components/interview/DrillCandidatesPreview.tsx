/**
 * [REQ-048 US2 T061 + US5 T103] DrillCandidatesPreview — preview 5 candidates
 * before commit. Now also renders the VariantToggle (US5) so the user can
 * opt into 变体重考 before committing the drill.
 *
 * Shows the 5 source_question_ids returned by ``GET /api/v1/interview-sessions/
 * quick-drill/preview`` with their dimension + a brief excerpt of question_text.
 *
 * This component is rendered in InterviewModeSelect.tsx as a modal before
 * the user commits to a quick_drill session (T062 wire).
 */
import { useEffect, useState } from 'react'
import { request } from '@/api/client'
import { VariantToggle } from './VariantToggle'

interface DrillCandidate {
  id?: string
  source_question_id?: string
  source_session_id?: string
  dimension?: string
  question_text?: string
}

interface DrillPreviewResponse {
  data: {
    candidates: DrillCandidate[]
    cache_key: string
    degraded: boolean
  }
}

interface DrillCandidatesPreviewProps {
  jdText?: string
  onConfirm: (useVariants: boolean, errorQuestionIds: string[]) => void
  onCancel: () => void
  testId?: string
}

export function DrillCandidatesPreview({
  jdText = '',
  onConfirm,
  onCancel,
  testId = 'drill-candidates-preview',
}: DrillCandidatesPreviewProps) {
  const [candidates, setCandidates] = useState<DrillCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [degraded, setDegraded] = useState(false)
  // REQ-048 US5 T103 — variant toggle state. Default false per AC-25 R22
  // (不传或 false 必须走原题重考).
  const [useVariants, setUseVariants] = useState(false)

  useEffect(() => {
    request<DrillPreviewResponse>({
      method: 'GET',
      path: '/api/v1/interview-sessions/quick-drill/preview',
      query: { jd_text: jdText || undefined },
    })
      .then((body) => {
        setCandidates(body.data?.candidates ?? [])
        setDegraded(body.data?.degraded ?? false)
        setLoading(false)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'unknown error')
        setLoading(false)
      })
  }, [jdText])

  const dimensions = new Set(candidates.map((c) => c.dimension).filter(Boolean))
  const candidateIds = candidates
    .map((c) => c.source_question_id ?? c.id)
    .filter((id): id is string => Boolean(id))

  return (
    <div
      data-testid={testId}
      className="mx-auto max-w-2xl space-y-4 rounded-lg border border-line bg-bg-1 p-6 shadow-lg"
    >
      <header>
        <h2 className="text-lg font-semibold text-ink-1">快速补漏预览</h2>
        <p className="mt-1 text-sm text-ink-3">
          以下是按你的岗位 + 错题本匹配出的 5 道题。
          {dimensions.size > 0 && (
            <>覆盖维度：
              {Array.from(dimensions).map((d) => (
                <span key={d} className="ml-1 inline-block rounded bg-bg-3 px-2 py-0.5 text-xs">
                  {d}
                </span>
              ))}
            </>
          )}
        </p>
      </header>

      {degraded && (
        <div
          role="alert"
          data-testid="drill-degraded-warning"
          className="rounded bg-warning-bg px-3 py-2 text-sm text-warning-fg"
        >
          错题匹配精度下降（embedding/rerank 服务降级）
        </div>
      )}

      {loading && (
        <div data-testid="drill-loading" className="text-sm text-ink-3">加载中…</div>
      )}
      {error && (
        <div role="alert" className="rounded bg-error-bg px-3 py-2 text-sm text-error-fg">
          {error}
        </div>
      )}

      {!loading && !error && (
        <ol className="space-y-2" data-testid="drill-candidates-list">
          {candidates.map((c, idx) => (
            <li
              key={c.source_question_id ?? c.id ?? idx}
              data-testid="drill-candidate"
              className="rounded border border-line bg-bg-2 px-3 py-2"
            >
              <div className="flex items-baseline justify-between">
                <span className="text-sm font-medium text-ink-1">
                  {idx + 1}. {(c.question_text ?? '').slice(0, 60)}
                  {(c.question_text ?? '').length > 60 && '…'}
                </span>
                {c.dimension && (
                  <span className="ml-2 text-xs text-ink-3">{c.dimension}</span>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}

      {/* REQ-048 US5 T103 — variant toggle. Default off (原题重考). */}
      <VariantToggle enabled={useVariants} onChange={setUseVariants} />

      <footer className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-line bg-bg-2 px-3 py-1.5 text-sm text-ink-2 hover:bg-bg-3"
          data-testid="drill-cancel"
        >
          取消
        </button>
        <button
          type="button"
          onClick={() => onConfirm(useVariants, candidateIds)}
          disabled={loading || candidates.length === 0}
          className="rounded bg-primary px-3 py-1.5 text-sm text-on-primary hover:bg-primary-hover disabled:opacity-50"
          data-testid="drill-confirm"
        >
          开始面试
        </button>
      </footer>
    </div>
  )
}

export default DrillCandidatesPreview

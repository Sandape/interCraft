/**
 * RevealRequestForm — REQ-044 FR-033 / AC-33.3.
 *
 * Form for submitting a sensitive reveal request:
 * - target_type: 5 sensitive categories (user_resume / user_interview /
 *   ai_prompt / ai_model_output / incident_payload).
 * - target_id: free-form target id.
 * - reason: ≥ 20 chars (server-side validation; we also disable
 *   submit until the client-side counter is ≥ 20).
 *
 * EC-1: when the server response is "denied", the form renders a
 * fullscreen "access denied" overlay with audit_event_id so the
 * surrounding trace drawer can be closed (parent component listens
 * via window CustomEvent "ic:reveal-denied" with detail.audit_event_id).
 */
import { useState } from 'react'
import type {
  RevealRequest,
  SensitiveTargetType,
} from '@/types/admin-governance'
import { useCreateRevealRequest } from '@/admin/hooks/queries/useGovernance'

const MIN_REASON_LENGTH = 20
const TARGET_TYPES: SensitiveTargetType[] = [
  'user_resume',
  'user_interview',
  'ai_prompt',
  'ai_model_output',
  'incident_payload',
]

interface Props {
  defaultTargetType?: SensitiveTargetType
  defaultTargetId?: string
  onSuccess?: (req: RevealRequest) => void
  onDenied?: (auditEventId: string, reason: string) => void
}

export function RevealRequestForm({
  defaultTargetType = 'user_resume',
  defaultTargetId = '',
  onSuccess,
  onDenied,
}: Props) {
  const [targetType, setTargetType] = useState<SensitiveTargetType>(
    defaultTargetType,
  )
  const [targetId, setTargetId] = useState<string>(defaultTargetId)
  const [reason, setReason] = useState<string>('')
  const [deniedInfo, setDeniedInfo] = useState<{
    auditEventId: string
    reason: string
  } | null>(null)

  const createMutation = useCreateRevealRequest()

  const trimmed = reason.trim()
  const reasonLen = trimmed.length
  const isValid =
    reasonLen >= MIN_REASON_LENGTH && targetId.trim().length >= 1

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!isValid) return
    createMutation.mutate(
      { target_type: targetType, target_id: targetId.trim(), reason: trimmed },
      {
        onSuccess: (req: RevealRequest) => {
          if (req.result === 'denied') {
            setDeniedInfo({
              auditEventId: req.audit_event_id,
              reason: req.reason,
            })
            onDenied?.(req.audit_event_id, req.reason)
            // EC-1: dispatch event so any open trace drawer can close
            window.dispatchEvent(
              new CustomEvent('ic:reveal-denied', {
                detail: {
                  audit_event_id: req.audit_event_id,
                  reason: req.reason,
                },
              }),
            )
          } else {
            onSuccess?.(req)
          }
        },
      },
    )
  }

  function closeDeniedBanner() {
    setDeniedInfo(null)
  }

  return (
    <form
      className="ac-gov-reveal__form"
      onSubmit={handleSubmit}
      data-testid="reveal-request-form"
    >
      <div className="ac-gov-reveal__field">
        <label
          className="ac-gov-reveal__label"
          htmlFor="reveal-target-type"
        >
          Target type
        </label>
        <select
          id="reveal-target-type"
          data-testid="reveal-target-type"
          className="ac-gov-reveal__select"
          value={targetType}
          onChange={(e) =>
            setTargetType(e.target.value as SensitiveTargetType)
          }
        >
          {TARGET_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div className="ac-gov-reveal__field">
        <label className="ac-gov-reveal__label" htmlFor="reveal-target-id">
          Target ID
        </label>
        <input
          id="reveal-target-id"
          data-testid="reveal-target-id"
          className="ac-gov-reveal__input"
          type="text"
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          placeholder="user-123 / prompt-001 / ..."
        />
      </div>

      <div className="ac-gov-reveal__field">
        <label className="ac-gov-reveal__label" htmlFor="reveal-reason">
          Reason (≥ 20 chars, server-enforced)
        </label>
        <textarea
          id="reveal-reason"
          data-testid="reveal-reason-textarea"
          className="ac-gov-reveal__textarea"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          minLength={MIN_REASON_LENGTH}
          placeholder="Justify the reveal — what are you investigating and why is the raw content necessary?"
        />
        <span
          className={
            'ac-gov-reveal__counter ' +
            (reasonLen === 0
              ? ''
              : reasonLen < MIN_REASON_LENGTH
                ? 'ac-gov-reveal__counter--err'
                : 'ac-gov-reveal__counter--ok')
          }
          data-testid="reveal-reason-counter"
          data-length={reasonLen}
        >
          {reasonLen} / {MIN_REASON_LENGTH}+ chars
        </span>
      </div>

      <button
        type="submit"
        className="ac-gov-reveal__submit"
        data-testid="reveal-submit"
        disabled={!isValid || createMutation.isPending}
      >
        {createMutation.isPending ? 'Submitting…' : 'Submit reveal request'}
      </button>

      {createMutation.isError ? (
        <div
          className="ac-error-banner"
          data-testid="reveal-error-banner"
          role="alert"
        >
          {String((createMutation.error as Error)?.message ?? 'reveal failed')}
        </div>
      ) : null}

      {deniedInfo ? (
        <div
          className="ac-gov-reveal__denied-banner"
          data-testid="reveal-denied-fullscreen"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="reveal-denied-title"
        >
          <h2 id="reveal-denied-title" style={{ fontSize: 18 }}>
            Access denied
          </h2>
          <p style={{ fontSize: 13, marginBottom: 12 }}>
            你的敏感内容查看请求已被拒绝。原因：
          </p>
          <pre data-testid="reveal-denied-audit-event-id">
            audit_event_id: {deniedInfo.auditEventId}
            {'\n'}reason: {deniedInfo.reason}
          </pre>
          <button
            type="button"
            onClick={closeDeniedBanner}
            data-testid="reveal-deny-dismiss"
            style={{
              marginTop: 16,
              padding: '8px 16px',
              border: 0,
              borderRadius: 4,
              background: 'white',
              color: '#0f172a',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Close trace drawer
          </button>
        </div>
      ) : null}
    </form>
  )
}

export default RevealRequestForm

/**
 * CommentList — REQ-044 US4 / FR-022 + AC-22.3.
 *
 * Renders the comment thread for an incident. Includes an inline
 * "Add comment" form (requires INCIDENT_CHANGE capability on the
 * backend; the page-level state decides whether to render the form
 * based on the current role's capabilities).
 */
import { useState } from 'react'
import type { Comment, CommentCreateRequest } from '@/types/admin-incidents'

interface CommentListProps {
  comments: Comment[]
  canAdd: boolean
  onAdd: (body: CommentCreateRequest) => Promise<unknown> | unknown
  isSubmitting?: boolean
}

function formatTime(ts: string): string {
  if (ts === 'unknown') return 'stale'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function CommentList({
  comments,
  canAdd,
  onAdd,
  isSubmitting,
}: CommentListProps) {
  const [draft, setDraft] = useState('')
  const [reason, setReason] = useState('')

  const submit = async () => {
    if (!draft.trim()) return
    await onAdd({ body: draft.trim(), reason: reason.trim() || null })
    setDraft('')
    setReason('')
  }

  return (
    <div className="ic-comments" data-testid="comment-list">
      {comments.length === 0 ? (
        <p
          className="ic-comments__empty"
          data-testid="comments-empty"
        >
          No comments yet
        </p>
      ) : (
        <ul className="ic-comments__list">
          {comments.map((c) => (
            <li
              key={c.id}
              className="ic-comments__item"
              data-testid={`comment-${c.id}`}
              data-comment-id={c.id}
              data-comment-actor={c.actor}
            >
              <header className="ic-comments__header">
                <span className="ic-comments__actor">{c.actor}</span>
                <span className="ic-comments__dot">·</span>
                <span className="ic-comments__time">
                  {formatTime(c.createdAt)}
                </span>
                {c.reason ? (
                  <span className="ic-comments__reason">
                    ({c.reason})
                  </span>
                ) : null}
              </header>
              <p className="ic-comments__body">{c.body}</p>
            </li>
          ))}
        </ul>
      )}
      {canAdd ? (
        <div
          className="ic-comments__compose"
          data-testid="comment-compose"
        >
          <label className="ic-comments__field">
            <span className="ic-comments__field-label">Comment</span>
            <textarea
              data-testid="comment-body"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type your comment…"
              rows={3}
            />
          </label>
          <label className="ic-comments__field">
            <span className="ic-comments__field-label">Reason (optional)</span>
            <input
              data-testid="comment-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why is this comment relevant?"
            />
          </label>
          <button
            type="button"
            className="ic-comments__submit"
            data-testid="comment-submit"
            onClick={submit}
            disabled={isSubmitting || !draft.trim()}
          >
            {isSubmitting ? 'Submitting…' : 'Add comment'}
          </button>
        </div>
      ) : null}
    </div>
  )
}

export default CommentList

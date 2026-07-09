/**
 * ModeCard — REQ-048 US1 (T037).
 *
 * Single mode card component: icon + title + description. Used in the
 * InterviewModeSelect page for the two top-level cards (在线 AI 面试 /
 * 豆包面试).
 */
import type { ReactNode } from 'react'

interface ModeCardProps {
  testId: string
  title: string
  description: string
  icon?: ReactNode
  onClick: () => void
}

export function ModeCard({ testId, title, description, icon, onClick }: ModeCardProps) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className="flex flex-col items-start gap-3 rounded-lg border border-line-2 bg-bg-1 p-6 text-left shadow-sm transition hover:border-line-1 hover:bg-bg-2"
    >
      {icon && <div className="text-2xl">{icon}</div>}
      <div>
        <h2 className="text-lg font-semibold text-ink-1">{title}</h2>
        <p className="mt-1 text-sm text-ink-3">{description}</p>
      </div>
    </button>
  )
}

export default ModeCard
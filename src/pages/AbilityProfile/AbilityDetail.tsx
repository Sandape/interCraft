/** AbilityDetail — self-assessment panel with slider and notes textarea. */
import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface Props {
  label: string
  currentScore: number
  idealScore: number
  onSubmit: (score: number, notes?: string) => void
  onClose: () => void
}

export default function AbilityDetail({ label, currentScore, idealScore, onSubmit, onClose }: Props) {
  const [score, setScore] = useState(currentScore)
  const [notes, setNotes] = useState('')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white dark:bg-dark-surface rounded-xl shadow-xl p-6 w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-ink-1">自评: {label}</h3>
          <button onClick={onClose} className="text-ink-3 hover:text-ink-1">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-ink-3">当前分数</span>
            <span className="text-xs text-ink-3">目标: {idealScore}</span>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={0}
              max={10}
              step={0.5}
              value={score}
              onChange={(e) => setScore(Number(e.target.value))}
              className="flex-1"
            />
            <span className="text-lg font-semibold text-brand-600 tabular-nums w-10 text-right">
              {score}
            </span>
          </div>
          <div className="flex justify-between text-2xs text-ink-4 mt-1">
            <span>0</span>
            <span>10</span>
          </div>
        </div>

        <div className="mb-4">
          <label className="text-xs text-ink-2 mb-1 block">备注 (可选)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="例如: 3 年后端开发经验..."
            className="w-full text-sm border border-surface-border dark:border-dark-surface-border rounded-lg p-2 resize-none h-20 bg-transparent text-ink-1 placeholder:text-ink-4 focus:outline-none focus:border-brand-500"
          />
        </div>

        <div className="flex gap-2">
          <Button variant="secondary" onClick={onClose} className="flex-1">
            取消
          </Button>
          <Button variant="primary" onClick={() => onSubmit(score, notes || undefined)} className="flex-1">
            提交自评
          </Button>
        </div>
      </div>
    </div>
  )
}

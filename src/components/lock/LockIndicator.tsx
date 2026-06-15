/** T041 — LockIndicator component.

Displays lock status badge: locked / readonly / idle.
*/
import React from 'react'

export interface LockIndicatorProps {
  status: 'idle' | 'acquiring' | 'locked' | 'readonly' | 'conflict'
  holder?: { userId: string; userName: string }
  onRelease?: () => void
  className?: string
}

export const LockIndicator: React.FC<LockIndicatorProps> = ({
  status,
  holder,
  onRelease,
  className = '',
}) => {
  if (status === 'idle') return null

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium ${className}`}
      role="status"
      aria-live="polite"
    >
      {status === 'locked' && (
        <span className="flex items-center gap-1.5 text-green-700 bg-green-50 border border-green-200 rounded px-2 py-1">
          <LockIcon />
          正在编辑
          {onRelease && (
            <button
              onClick={onRelease}
              className="ml-2 text-xs text-green-600 hover:text-green-800 underline"
              aria-label="释放锁"
            >
              释放
            </button>
          )}
        </span>
      )}

      {status === 'acquiring' && (
        <span className="flex items-center gap-1.5 text-yellow-700 bg-yellow-50 border border-yellow-200 rounded px-2 py-1">
          <span className="animate-pulse">获取锁中...</span>
        </span>
      )}

      {status === 'readonly' && (
        <span className="flex items-center gap-1.5 text-orange-700 bg-orange-50 border border-orange-200 rounded px-2 py-1">
          <LockIcon />
          只读
          {holder && <> · {holder.userName} 正在编辑</>}
        </span>
      )}

      {status === 'conflict' && (
        <span className="flex items-center gap-1.5 text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">
          <span>⚠ 冲突</span>
        </span>
      )}
    </div>
  )
}

function LockIcon() {
  return (
    <svg
      className="w-4 h-4"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 2C9.243 2 7 4.243 7 7v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7c0-2.757-2.243-5-5-5zM9 7c0-1.654 1.346-3 3-3s3 1.346 3 3v3H9V7z" />
    </svg>
  )
}

export default LockIndicator

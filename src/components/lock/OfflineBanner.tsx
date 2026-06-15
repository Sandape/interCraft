/** T042 — OfflineBanner component.

Displays a fixed bottom banner when offline or syncing.
*/
import React, { useEffect, useState } from 'react'
import { outboxReplayService } from '../../lib/outbox/OutboxReplayService'

export interface OfflineBannerProps {
  onConflictClick?: () => void
}

export const OfflineBanner: React.FC<OfflineBannerProps> = ({
  onConflictClick,
}) => {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [pendingCount, setPendingCount] = useState(0)
  const [conflictCount, setConflictCount] = useState(0)
  const [isSyncing, setIsSyncing] = useState(false)

  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  useEffect(() => {
    const interval = setInterval(async () => {
      const count = await outboxReplayService.pendingCount
      setPendingCount(count)
      const conflicts = await (
        await import('../../lib/outbox/OutboxRepository')
      ).outboxRepo.countByStatus('conflict')
      setConflictCount(conflicts)
    }, 5_000)
    return () => clearInterval(interval)
  }, [])

  // Hook into replay service for syncing state
  useEffect(() => {
    outboxReplayService.startWatching()
    return () => outboxReplayService.stopWatching()
  }, [])

  if (isOnline && pendingCount === 0 && conflictCount === 0) return null

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-center py-2 px-4 text-sm font-medium"
      role="alert"
      aria-live="polite"
    >
      {!isOnline && pendingCount > 0 && (
        <span className="flex items-center gap-2 bg-yellow-100 border border-yellow-300 text-yellow-800 rounded-md px-4 py-2">
          <OfflineIcon />
          离线 · 已暂存 {pendingCount} 条
        </span>
      )}

      {isOnline && isSyncing && (
        <span className="flex items-center gap-2 bg-blue-100 border border-blue-300 text-blue-800 rounded-md px-4 py-2">
          <span className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
          同步中...
        </span>
      )}

      {isOnline && conflictCount > 0 && (
        <button
          onClick={onConflictClick}
          className="flex items-center gap-2 bg-red-100 border border-red-300 text-red-800 rounded-md px-4 py-2 cursor-pointer hover:bg-red-200"
        >
          <WarningIcon />
          {conflictCount} 条冲突需处理
        </button>
      )}
    </div>
  )
}

function OfflineIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm-1 5v4h2V7h-2zm0 6v2h2v-2h-2z" />
    </svg>
  )
}

function WarningIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
    </svg>
  )
}

export default OfflineBanner

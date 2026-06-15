/** AbilityUpdateStatus — M18 status indicator for ability diagnose updates. */
import { Loader2, CheckCircle } from 'lucide-react'
import { useAbilityDiagnose } from '@/hooks/useAbilityDiagnose'

interface AbilityUpdateStatusProps {
  userId: string | null
}

export default function AbilityUpdateStatus({ userId }: AbilityUpdateStatusProps) {
  const { updating, updated, summary } = useAbilityDiagnose(userId)

  if (!updating && !updated) return null

  return (
    <div
      className="flex items-center gap-2 px-3 py-2 rounded-md bg-surface-muted dark:bg-dark-surface-muted"
      data-testid="ability-update-status"
      data-updating={updating}
      data-updated={updated}
    >
      {updating && (
        <>
          <Loader2 className="h-4 w-4 animate-spin text-brand-500" />
          <span className="text-xs text-ink-2" data-testid="ability-update-status-text">能力画像更新中…</span>
        </>
      )}
      {updated && (
        <>
          <CheckCircle className="h-4 w-4 text-success-500" />
          <span className="text-xs text-ink-2" data-testid="ability-update-status-text">
            {summary || '能力画像已更新'}
          </span>
        </>
      )}
    </div>
  )
}

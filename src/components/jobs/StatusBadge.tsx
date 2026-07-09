import { Badge } from '@/components/ui/Badge'
import {
  Briefcase,
  CheckCircle2,
  Clock,
  FileText,
  MessageSquare,
  XCircle,
} from 'lucide-react'
import { JOB_STATUS_LABELS } from '@/types/jobs'

/**
 * REQ-053 (T028) — Status badge driven by the canonical JOB_STATUS_LABELS map
 * (source: `GET /api/v1/jobs/transitions`). Terminal states (failed/passed) get
 * distinct variants so they stand out from active interview rounds.
 */
const statusConfig: Record<
  string,
  { variant: 'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline'; icon: typeof Briefcase }
> = {
  wishlist: { variant: 'default', icon: Clock },
  applied: { variant: 'brand', icon: FileText },
  test: { variant: 'default', icon: FileText },
  interview_1: { variant: 'warning', icon: MessageSquare },
  interview_2: { variant: 'warning', icon: MessageSquare },
  interview_3: { variant: 'warning', icon: MessageSquare },
  // legacy fallbacks — kept so old data still renders something sensible.
  oa: { variant: 'default', icon: FileText },
  hr: { variant: 'warning', icon: MessageSquare },
  offer: { variant: 'success', icon: CheckCircle2 },
  failed: { variant: 'danger', icon: XCircle },
  passed: { variant: 'success', icon: CheckCircle2 },
  rejected: { variant: 'danger', icon: XCircle },
  withdrawn: { variant: 'outline', icon: XCircle },
}

export function JobStatusBadge({ status, testId }: { status: string; testId?: string }) {
  const cfg = statusConfig[status] ?? {
    variant: 'default' as const,
    icon: Briefcase,
  }
  const label = JOB_STATUS_LABELS[status] ?? status
  return (
    <span data-testid={testId}>
      <Badge variant={cfg.variant} leftIcon={<cfg.icon className="h-2.5 w-2.5" />}>
        {label}
      </Badge>
    </span>
  )
}

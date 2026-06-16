import { Badge } from '@/components/ui/Badge'
import { Briefcase, CheckCircle2, Clock, FileText, MessageSquare, XCircle } from 'lucide-react'

const statusConfig: Record<string, { label: string; variant: 'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline'; icon: typeof Briefcase }> = {
  wishlist: { label: '关注中', variant: 'default', icon: Clock },
  applied: { label: '已投递', variant: 'brand', icon: FileText },
  test: { label: '笔试', variant: 'default', icon: FileText },
  oa: { label: 'OA', variant: 'default', icon: FileText },
  hr: { label: 'HR 面', variant: 'warning', icon: MessageSquare },
  offer: { label: 'Offer', variant: 'success', icon: CheckCircle2 },
  rejected: { label: '已拒绝', variant: 'danger', icon: XCircle },
  withdrawn: { label: '已撤回', variant: 'outline', icon: XCircle },
}

export function JobStatusBadge({ status, testId }: { status: string; testId?: string }) {
  const cfg = statusConfig[status] ?? { label: status, variant: 'default' as const, icon: Briefcase }
  return (
    <span data-testid={testId}>
      <Badge variant={cfg.variant} leftIcon={<cfg.icon className="h-2.5 w-2.5" />}>
        {cfg.label}
      </Badge>
    </span>
  )
}

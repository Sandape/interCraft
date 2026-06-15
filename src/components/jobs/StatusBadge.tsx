import { Badge } from '@/components/ui/Badge'
import { Briefcase, CheckCircle2, Clock, FileText, Filter, MessageSquare, XCircle } from 'lucide-react'

const statusConfig: Record<string, { label: string; variant: 'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline'; icon: typeof Briefcase }> = {
  wishlist: { label: '关注中', variant: 'default', icon: Clock },
  applied: { label: '已投递', variant: 'brand', icon: FileText },
  screening: { label: '简历筛选', variant: 'warning', icon: Filter },
  interview: { label: '面试中', variant: 'brand', icon: MessageSquare },
  offer: { label: 'Offer', variant: 'success', icon: CheckCircle2 },
  rejected: { label: '已拒绝', variant: 'danger', icon: XCircle },
}

export function JobStatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status] ?? { label: status, variant: 'default' as const, icon: Briefcase }
  return (
    <Badge variant={cfg.variant} leftIcon={<cfg.icon className="h-2.5 w-2.5" />}>
      {cfg.label}
    </Badge>
  )
}

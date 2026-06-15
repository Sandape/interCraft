import { Badge } from '@/components/ui/Badge'
import { AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react'

const statusConfig: Record<string, { label: string; variant: 'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline'; icon: typeof AlertCircle }> = {
  fresh: { label: '未掌握', variant: 'danger', icon: AlertCircle },
  practicing: { label: '练习中', variant: 'warning', icon: RefreshCw },
  mastered: { label: '已掌握', variant: 'success', icon: CheckCircle2 },
}

export function StatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status] ?? { label: status, variant: 'default' as const, icon: AlertCircle }
  return (
    <Badge variant={cfg.variant} leftIcon={<cfg.icon className="h-2.5 w-2.5" />}>
      {cfg.label}
    </Badge>
  )
}

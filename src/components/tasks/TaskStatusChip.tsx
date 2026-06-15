import { Badge } from '@/components/ui/Badge'

const statusConfig: Record<string, { label: string; variant: 'default' | 'brand' | 'success' | 'warning' | 'danger' | 'outline' }> = {
  todo: { label: '待办', variant: 'default' },
  doing: { label: '进行中', variant: 'brand' },
  done: { label: '已完成', variant: 'success' },
  archived: { label: '已归档', variant: 'outline' },
}

export function TaskStatusChip({ status }: { status: string }) {
  const cfg = statusConfig[status] ?? { label: status, variant: 'default' as const }
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>
}

import { Badge } from '@/components/ui/Badge'

export function FrequencyBadge({ frequency }: { frequency: number }) {
  const variant = frequency >= 4 ? 'danger' : frequency >= 2 ? 'warning' : 'default'
  return (
    <Badge variant={variant}>
      {frequency >= 4 ? '高频' : frequency >= 2 ? '中频' : '低频'} · {frequency}次
    </Badge>
  )
}

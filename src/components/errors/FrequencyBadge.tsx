import { Badge } from '@/components/ui/Badge'

export function FrequencyBadge({ frequency }: { frequency: number }) {
  const variant = frequency >= 3 ? 'danger' : frequency >= 1 ? 'warning' : 'success'
  const label = frequency >= 3 ? '高频' : frequency >= 1 ? '复习中' : '已清零'

  return (
    <Badge variant={variant}>
      {label} · {frequency} 次
    </Badge>
  )
}

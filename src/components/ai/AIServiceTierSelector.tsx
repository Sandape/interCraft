/**
 * REQ-061 US7 / T108 — standard/quality tier selector with degradation consent.
 * Users never see provider/model vendor names — only stable tier labels.
 */
import { cn } from '@/lib/utils'

export type ServiceTier = 'standard' | 'quality'

export interface AIServiceTierSelectorProps {
  value: ServiceTier
  onChange: (tier: ServiceTier) => void
  allowDegrade?: boolean
  onAllowDegradeChange?: (allow: boolean) => void
  disabled?: boolean
  pointCapHint?: { standard?: number; quality?: number }
  className?: string
}

const TIERS: {
  id: ServiceTier
  title: string
  description: string
}[] = [
  {
    id: 'standard',
    title: '标准',
    description: '稳定默认档位，适合大多数任务',
  },
  {
    id: 'quality',
    title: '高质量',
    description: '更高质量承诺，点数上限通常更高',
  },
]

export function AIServiceTierSelector({
  value,
  onChange,
  allowDegrade = false,
  onAllowDegradeChange,
  disabled = false,
  pointCapHint,
  className,
}: AIServiceTierSelectorProps) {
  return (
    <div
      className={cn('space-y-3', className)}
      data-testid="ai-service-tier-selector"
    >
      <div className="grid gap-2 sm:grid-cols-2">
        {TIERS.map((tier) => {
          const selected = value === tier.id
          const cap = pointCapHint?.[tier.id]
          return (
            <button
              key={tier.id}
              type="button"
              disabled={disabled}
              data-testid={`ai-service-tier-${tier.id}`}
              aria-pressed={selected}
              onClick={() => onChange(tier.id)}
              className={cn(
                'rounded-lg border px-3 py-3 text-left transition-colors',
                selected
                  ? 'border-brand-500 bg-brand-50/60 ring-1 ring-brand-500'
                  : 'border-line-2 hover:border-line-1',
                disabled && 'opacity-60 cursor-not-allowed',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-ink-1">{tier.title}</span>
                {typeof cap === 'number' ? (
                  <span
                    className="text-xs text-ink-3"
                    data-testid={`ai-service-tier-cap-${tier.id}`}
                  >
                    上限 {cap} 点
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-xs text-ink-3">{tier.description}</p>
            </button>
          )
        })}
      </div>

      {onAllowDegradeChange ? (
        <label
          className="flex items-start gap-2 text-sm text-ink-2"
          data-testid="ai-service-tier-degrade"
        >
          <input
            type="checkbox"
            className="mt-0.5"
            checked={allowDegrade}
            disabled={disabled}
            onChange={(e) => onAllowDegradeChange(e.target.checked)}
            data-testid="ai-service-tier-degrade-input"
          />
          <span>
            允许在质量门失败时降级到可用结果（仍按受理时的档位与点数承诺结算）
          </span>
        </label>
      ) : null}
    </div>
  )
}

export default AIServiceTierSelector

/**
 * REQ-061 T098 — proactive research opt-in / quote / sources / cancel / task links.
 */
import { Link } from 'react-router-dom'
import { AIServiceTierSelector, type ServiceTier } from '@/components/ai/AIServiceTierSelector'
import { Button } from '@/components/ui/Button'

export interface ResearchQuotePreview {
  service_tier?: ServiceTier | string
  point_cap?: number
  quoted_max?: number
}

export interface ResearchSource {
  title: string
  url?: string | null
}

export interface InterviewResearchControlProps {
  sessionId: string
  enabled: boolean
  quote?: ResearchQuotePreview | null
  sources?: ResearchSource[]
  status?: 'idle' | 'quoted' | 'running' | 'succeeded' | 'failed' | 'cancelled' | string
  taskId?: string | null
  failureMessage?: string | null
  tier?: ServiceTier
  onTierChange?: (tier: ServiceTier) => void
  onOptIn: () => void
  onDisable: () => void
  onCancel: () => void
}

export function InterviewResearchControl({
  sessionId,
  enabled,
  quote,
  sources = [],
  status = 'idle',
  taskId = null,
  failureMessage = null,
  tier = 'standard',
  onTierChange,
  onOptIn,
  onDisable,
  onCancel,
}: InterviewResearchControlProps) {
  const pointCap = quote?.quoted_max ?? quote?.point_cap

  return (
    <section
      className="space-y-3 rounded-lg border border-surface-border p-4"
      data-testid="interview-research-control"
      data-session-id={sessionId}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink-1">主动研究（可选）</h3>
          <p className="mt-1 text-xs text-ink-3">需明确确认后才会接受报价并消耗点数。</p>
        </div>
        {enabled ? (
          <Button variant="ghost" size="sm" onClick={onDisable} data-testid="research-disable">
            关闭研究
          </Button>
        ) : (
          <Button variant="secondary" size="sm" onClick={onOptIn} data-testid="research-opt-in">
            开启并报价
          </Button>
        )}
      </div>

      {enabled && (
        <>
          {onTierChange && (
            <AIServiceTierSelector
              value={tier}
              onChange={onTierChange}
              pointCapHint={{
                standard: quote?.service_tier === 'quality' ? undefined : pointCap,
                quality: quote?.service_tier === 'quality' ? pointCap : undefined,
              }}
            />
          )}
          <div className="text-xs text-ink-3" data-testid="research-tier">
            档位：{quote?.service_tier ?? tier}
          </div>
          {typeof pointCap === 'number' && (
            <div className="text-sm" data-testid="research-point-preview">
              预计点数上限 {pointCap}
            </div>
          )}
          {sources.length > 0 && (
            <ul className="space-y-1 text-sm" data-testid="research-sources">
              {sources.map((s) => (
                <li key={s.url || s.title} data-testid="research-source">
                  {s.url ? (
                    <a href={s.url} className="underline" target="_blank" rel="noreferrer">
                      {s.title}
                    </a>
                  ) : (
                    s.title
                  )}
                </li>
              ))}
            </ul>
          )}
          {(status === 'running' || status === 'quoted') && (
            <Button variant="ghost" size="sm" onClick={onCancel} data-testid="research-cancel">
              取消研究
            </Button>
          )}
          {status === 'failed' && (
            <>
              <div role="alert" className="text-sm text-amber-800" data-testid="research-failure">
                {failureMessage || '研究失败'}
              </div>
              <Button variant="ghost" size="sm" onClick={onCancel} data-testid="research-cancel">
                关闭失败任务
              </Button>
            </>
          )}
          {taskId && (
            <Link
              to={`/ai-tasks/${encodeURIComponent(taskId)}`}
              className="inline-flex text-xs text-brand-600 underline"
              data-testid="research-task-link"
            >
              查看研究任务
            </Link>
          )}
        </>
      )}
    </section>
  )
}

export default InterviewResearchControl

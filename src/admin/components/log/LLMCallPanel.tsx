/**
 * LLMCallPanel — REQ-044 US5 / FR-026 + FR-027 / AC-26.1 + AC-26.3 + AC-26.5 + AC-26.6.
 *
 * Renders one LLMCall detail with:
 * - model / input_tokens / output_tokens / cache_hit / latency / cache_key fingerprint
 * - raw_prompt + raw_model_output masked by default ("permission: hidden")
 * - "Request Reveal" button → /admin-console/governance?reveal=llm_call:{id}
 *
 * cache_key_fingerprint reuse FR-027 prompt caching.
 */
import type { LLMCall } from '@/types/admin-logs'
import { formatDuration } from './index'

interface LLMCallPanelProps {
  llmCall: LLMCall
  onRequestReveal?: (targetType: 'llm_call', targetId: string) => void
}

function buildRevealHref(callId: string): string {
  return `/admin-console/governance?reveal=${encodeURIComponent(`llm_call:${callId}`)}`
}

export function LLMCallPanel({ llmCall, onRequestReveal }: LLMCallPanelProps) {
  return (
    <article
      className="ac-llm-call-panel"
      data-testid="llm-call-panel"
      data-llm-call-id={llmCall.id}
    >
      <header className="ac-llm-call-panel__head">
        <h4 className="ac-llm-call-panel__title" data-testid="llm-call-model">
          {llmCall.model}
        </h4>
        {llmCall.cacheHit ? (
          <span
            className="ac-status ac-status--pending"
            data-testid="llm-call-cache-hit"
          >
            cache hit
          </span>
        ) : (
          <span
            className="ac-status ac-status--success"
            data-testid="llm-call-cache-miss"
          >
            cache miss
          </span>
        )}
      </header>

      <dl className="ac-llm-call-panel__fields">
        <dt>started</dt>
        <dd data-testid="llm-call-started-at">{llmCall.startedAt}</dd>
        <dt>latency</dt>
        <dd data-testid="llm-call-latency">{formatDuration(llmCall.latencyMs)}</dd>
        <dt>input_tokens</dt>
        <dd data-testid="llm-call-input-tokens">{llmCall.inputTokens}</dd>
        <dt>output_tokens</dt>
        <dd data-testid="llm-call-output-tokens">{llmCall.outputTokens}</dd>
        <dt>cache_key_fingerprint</dt>
        <dd
          className="ac-mono"
          data-testid="llm-call-cache-key-fingerprint"
        >
          {llmCall.cacheKeyFingerprint}
        </dd>
      </dl>

      <section className="ac-llm-call-panel__payload" data-testid="llm-call-payload">
        <h5>raw_prompt / raw_model_output</h5>
        <p
          className="ac-llm-call-panel__masked"
          data-testid="llm-call-payload-masked"
        >
          permission: hidden — 5 类敏感字段 (raw_prompt / raw_model_output / raw_input
          / raw_output / redaction_token) 默认 masked
        </p>
      </section>

      <footer className="ac-llm-call-panel__actions">
        <a
          href={buildRevealHref(llmCall.id)}
          className="ac-btn ac-btn--ghost"
          data-testid={`llm-call-request-reveal-${llmCall.id}`}
          onClick={(e) => {
            // We still navigate via window.location so US6 picks up
            // the reveal= query param. Prevent React Router from
            // intercepting so the URL is shareable as-is.
            if (onRequestReveal) {
              e.preventDefault()
              onRequestReveal('llm_call', llmCall.id)
              window.location.href = buildRevealHref(llmCall.id)
            }
          }}
        >
          Request Reveal
        </a>
      </footer>
    </article>
  )
}

export default LLMCallPanel
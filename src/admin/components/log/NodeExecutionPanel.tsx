/**
 * NodeExecutionPanel — REQ-044 US5 / FR-026 / AC-26.1 + AC-26.2.
 *
 * Renders one NodeExecution as a structured card with:
 * - timestamp / duration / status / retry_count
 * - version_context (model + prompt_fingerprint + rubric_version + app_version)
 * - nested tool + LLM call previews (link out to dedicated panels)
 * - sensitive payload masked by default; "Request Reveal" jump to US6
 */
import type { NodeExecution, VersionContext } from '@/types/admin-logs'
import { formatDuration } from './index'

interface NodeExecutionPanelProps {
  node: NodeExecution
  versionContext: VersionContext
  onOpenLlmCall?: (llmCallId: string) => void
  onOpenToolCall?: (toolCallId: string) => void
  onRequestReveal?: (targetType: 'agent_run' | 'node', targetId: string) => void
}

const STATUS_CLASS: Record<NodeExecution['status'], string> = {
  success: 'ac-status--success',
  failed: 'ac-status--failed',
  running: 'ac-status--running',
  pending: 'ac-status--pending',
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString()
}

export function NodeExecutionPanel({
  node,
  versionContext,
  onOpenLlmCall,
  onOpenToolCall,
  onRequestReveal,
}: NodeExecutionPanelProps) {
  return (
    <article
      className="ac-node-execution-panel"
      data-testid="node-execution-panel"
      data-node-id={node.id}
      data-node-name={node.nodeName}
    >
      <header className="ac-node-execution-panel__head">
        <div className="ac-node-execution-panel__title-row">
          <h4 className="ac-node-execution-panel__title">{node.nodeName}</h4>
          <span
            className={`ac-status ${STATUS_CLASS[node.status]}`}
            data-testid="node-status"
          >
            {node.status}
          </span>
        </div>
        <dl className="ac-node-execution-panel__meta">
          <dt>started</dt>
          <dd data-testid="node-started-at">{formatTimestamp(node.startedAt)}</dd>
          <dt>duration</dt>
          <dd data-testid="node-duration">{formatDuration(node.durationMs)}</dd>
          <dt>retry_count</dt>
          <dd data-testid="node-retry-count">{node.retryCount}</dd>
        </dl>
      </header>

      <section className="ac-node-execution-panel__version" data-testid="version-context">
        <h5>version context</h5>
        <dl>
          <dt>model</dt>
          <dd data-testid="version-model">{versionContext.model}</dd>
          <dt>prompt_fingerprint</dt>
          <dd data-testid="version-prompt-fingerprint">
            {versionContext.promptFingerprint}
          </dd>
          <dt>rubric_version</dt>
          <dd data-testid="version-rubric-version">{versionContext.rubricVersion}</dd>
          <dt>app_version</dt>
          <dd data-testid="version-app-version">{versionContext.appVersion}</dd>
        </dl>
      </section>

      {node.toolCalls.length > 0 && (
        <section className="ac-node-execution-panel__subgroup" data-testid="node-tool-calls">
          <h5>tool calls ({node.toolCalls.length})</h5>
          <ul>
            {node.toolCalls.map((t) => (
              <li key={t.id} data-testid={`node-tool-call-${t.id}`}>
                <button
                  type="button"
                  className="ac-link"
                  onClick={() => onOpenToolCall?.(t.id)}
                  data-testid={`open-tool-call-${t.id}`}
                >
                  {t.toolName}
                </button>
                <span className="ac-mono">{t.inputSchemaRef}</span>
                {t.error ? (
                  <span
                    className="ac-status ac-status--failed"
                    data-testid={`node-tool-error-${t.id}`}
                  >
                    error: {t.error}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      )}

      {node.llmCalls.length > 0 && (
        <section className="ac-node-execution-panel__subgroup" data-testid="node-llm-calls">
          <h5>LLM calls ({node.llmCalls.length})</h5>
          <ul>
            {node.llmCalls.map((c) => (
              <li key={c.id} data-testid={`node-llm-call-${c.id}`}>
                <button
                  type="button"
                  className="ac-link"
                  onClick={() => onOpenLlmCall?.(c.id)}
                  data-testid={`open-llm-call-${c.id}`}
                >
                  {c.model}
                </button>
                <span className="ac-mono">
                  in {c.inputTokens} / out {c.outputTokens}
                </span>
                {c.cacheHit ? (
                  <span
                    className="ac-status ac-status--pending"
                    data-testid={`node-llm-cache-hit-${c.id}`}
                  >
                    cache hit
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="ac-node-execution-panel__actions">
        <button
          type="button"
          className="ac-btn ac-btn--ghost"
          onClick={() => onRequestReveal?.('node', node.id)}
          data-testid={`node-request-reveal-${node.id}`}
        >
          Request Reveal
        </button>
      </footer>
    </article>
  )
}

export default NodeExecutionPanel
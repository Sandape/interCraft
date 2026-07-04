/**
 * ToolCallPanel — REQ-044 US5 / FR-026 / AC-26.1 + AC-26.4.
 *
 * Renders one ToolCall detail with:
 * - tool_name + input_schema_ref
 * - output_summary (truncated)
 * - error (if any)
 * - masked input/output payload + "Request Reveal" jump to US6
 */
import type { ToolCall } from '@/types/admin-logs'
import { formatDuration } from './index'

interface ToolCallPanelProps {
  toolCall: ToolCall
  onRequestReveal?: (targetType: 'tool_call', targetId: string) => void
}

export function ToolCallPanel({ toolCall, onRequestReveal }: ToolCallPanelProps) {
  return (
    <article
      className="ac-tool-call-panel"
      data-testid="tool-call-panel"
      data-tool-call-id={toolCall.id}
    >
      <header className="ac-tool-call-panel__head">
        <h4 className="ac-tool-call-panel__title" data-testid="tool-call-name">
          {toolCall.toolName}
        </h4>
        <span className="ac-mono ac-tool-call-panel__schema">
          {toolCall.inputSchemaRef}
        </span>
      </header>

      <dl className="ac-tool-call-panel__fields">
        <dt>started</dt>
        <dd data-testid="tool-call-started-at">{toolCall.startedAt}</dd>
        <dt>duration</dt>
        <dd data-testid="tool-call-duration">
          {formatDuration(
            toolCall.endedAt
              ? new Date(toolCall.endedAt).getTime() -
                  new Date(toolCall.startedAt).getTime()
              : null,
          )}
        </dd>
        <dt>output_summary</dt>
        <dd data-testid="tool-call-output-summary">{toolCall.outputSummary}</dd>
        {toolCall.error ? (
          <>
            <dt>error</dt>
            <dd
              className="ac-tool-call-panel__error"
              data-testid="tool-call-error"
            >
              {toolCall.error}
            </dd>
          </>
        ) : null}
      </dl>

      <section className="ac-tool-call-panel__payload" data-testid="tool-call-payload">
        <h5>raw input / output</h5>
        <p
          className="ac-tool-call-panel__masked"
          data-testid="tool-call-payload-masked"
        >
          permission: hidden — 需要 reveal 才能查看原始 payload
        </p>
      </section>

      <footer className="ac-tool-call-panel__actions">
        <button
          type="button"
          className="ac-btn ac-btn--ghost"
          onClick={() => onRequestReveal?.('tool_call', toolCall.id)}
          data-testid={`tool-call-request-reveal-${toolCall.id}`}
        >
          Request Reveal
        </button>
      </footer>
    </article>
  )
}

export default ToolCallPanel
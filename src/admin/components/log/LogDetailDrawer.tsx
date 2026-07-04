/**
 * LogDetailDrawer — REQ-044 US5 / FR-026 / AC-26.1 + AC-26.5 + AC-26.6 + EC-1.
 *
 * Deep-detail drawer for a single log event in the drilldown flow.
 * Renders:
 * - 4-panel layout: agent_run / node / tool_call / llm_call
 * - Each panel shows structured fields (per AC-26.1..26.4)
 * - Sensitive payload (raw_prompt / raw_model_output / raw_input /
 *   raw_output / redaction_token) masked by default per AC-26.5
 * - "Request Reveal" link → /admin-console/governance?reveal=… per AC-26.6
 * - EC-1: listens to window CustomEvent "ic:reveal-denied" → closes
 *   the drawer and surfaces an "access denied" banner.
 */
import { useEffect, useState } from 'react'
import { X, ShieldAlert } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { adminLogsApi } from '@/api/admin-logs'
import type { AgentRun, LogEvent } from '@/types/admin-logs'
import { NodeExecutionPanel } from './NodeExecutionPanel'
import { ToolCallPanel } from './ToolCallPanel'
import { LLMCallPanel } from './LLMCallPanel'
import { SharedByIncidentList } from './SharedByIncidentList'

interface LogDetailDrawerProps {
  open: boolean
  log: LogEvent | null
  onClose: () => void
}

const MASKED_LABEL = 'permission: hidden'

function buildRevealHref(targetType: string, targetId: string): string {
  return `/admin-console/governance?reveal=${encodeURIComponent(
    `${targetType}:${targetId}`,
  )}`
}

export function LogDetailDrawer({ open, log, onClose }: LogDetailDrawerProps) {
  // EC-1: when reveal is denied, the surrounding trace drawer closes
  // and an "access denied" banner is shown for ~5s.
  const [deniedBanner, setDeniedBanner] = useState<string | null>(null)
  useEffect(() => {
    function onRevealDenied(e: Event) {
      const detail = (e as CustomEvent<{ audit_event_id?: string; reason?: string }>).detail
      const reason = detail?.reason ?? 'unknown'
      setDeniedBanner(`access denied (${reason})`)
      onClose()
      setTimeout(() => setDeniedBanner(null), 5000)
    }
    window.addEventListener('ic:reveal-denied', onRevealDenied)
    return () => window.removeEventListener('ic:reveal-denied', onRevealDenied)
  }, [onClose])

  // FR-026 — fetch the agent run for the log's agentRunId. Mock until
  // OTel backend lands.
  const agentRunQuery = useQuery<AgentRun | null>({
    queryKey: ['admin', 'agent-run', log?.agentRunId],
    enabled: Boolean(open && log?.agentRunId),
    queryFn: async () => {
      if (!log?.agentRunId) return null
      return adminLogsApi.getAgentRun(log.agentRunId)
    },
  })

  const sharedByQuery = useQuery({
    queryKey: ['admin', 'shared-by-incidents', agentRunQuery.data?.traceId],
    enabled: Boolean(open && agentRunQuery.data?.traceId),
    queryFn: async () => {
      if (!agentRunQuery.data?.traceId) return { traceId: '', sharedBy: [] }
      return adminLogsApi.getSharedByIncidents(agentRunQuery.data.traceId)
    },
  })

  if (!open || !log) {
    // EC-1: when the drawer is closed (after a denied reveal), keep
    // the access-denied banner mounted for the duration of the
    // timeout so the user can read the audit event id.
    if (deniedBanner) {
      return (
        <div
          className="ac-log-detail-drawer__denied"
          data-testid="log-detail-drawer-denied"
          role="alert"
        >
          <ShieldAlert size={14} /> {deniedBanner}
        </div>
      )
    }
    return null
  }

  const agentRun = agentRunQuery.data ?? null

  return (
    <>
      <div
        className="ds-drawer__backdrop"
        data-testid="log-detail-drawer-backdrop"
        onClick={onClose}
      />
      <aside
        className="ds-drawer ac-log-detail-drawer"
        data-testid="log-detail-drawer"
        data-log-id={log.id}
        data-correlation-id={log.correlationId}
        role="dialog"
        aria-label={`Log detail ${log.id}`}
      >
        <header className="ds-drawer__header">
          <div className="ds-drawer__header-row">
            <h2 className="ds-drawer__title" data-testid="log-detail-title">
              {log.id}
            </h2>
            <button
              type="button"
              className="ds-drawer__close"
              onClick={onClose}
              data-testid="log-detail-drawer-close"
              aria-label="Close"
            >
              <X size={14} />
            </button>
          </div>
          <div className="ds-drawer__meta-row">
            <span className="ds-drawer__category">{log.source}</span>
            <span className="ds-drawer__freshness">{log.timestamp}</span>
            <span
              className={`ac-status ac-status--${log.level === 'error' ? 'failed' : log.level === 'warn' ? 'pending' : 'success'}`}
              data-testid="log-detail-level"
            >
              {log.level}
            </span>
          </div>
        </header>

        {deniedBanner ? (
          <div
            className="ac-log-detail-drawer__denied"
            data-testid="log-detail-drawer-denied"
            role="alert"
          >
            <ShieldAlert size={14} /> {deniedBanner}
          </div>
        ) : null}

        <div className="ac-log-detail-drawer__body">
          <section className="ac-log-detail-drawer__section" data-testid="log-detail-message">
            <h3>message</h3>
            <p>{log.message}</p>
          </section>

          <section
            className="ac-log-detail-drawer__section"
            data-testid="log-detail-correlation"
          >
            <h3>correlation_id</h3>
            <code className="ac-mono">{log.correlationId}</code>
          </section>

          <SharedByIncidentList refs={sharedByQuery.data?.sharedBy ?? []} />

          {agentRun ? (
            <>
              <section
                className="ac-log-detail-drawer__section"
                data-testid="log-detail-agent-run"
              >
                <h3>agent_run</h3>
                <dl>
                  <dt>id</dt>
                  <dd data-testid="agent-run-id">{agentRun.id}</dd>
                  <dt>graph</dt>
                  <dd data-testid="agent-run-graph">{agentRun.graphName}</dd>
                  <dt>duration</dt>
                  <dd data-testid="agent-run-duration">{agentRun.durationMs} ms</dd>
                  <dt>status</dt>
                  <dd data-testid="agent-run-status">{agentRun.status}</dd>
                </dl>
              </section>

              <section
                className="ac-log-detail-drawer__panels"
                data-testid="log-detail-panels"
              >
                {agentRun.nodeExecutions.map((n) => (
                  <NodeExecutionPanel
                    key={n.id}
                    node={n}
                    versionContext={agentRun.versionContext}
                    onRequestReveal={(targetType, targetId) => {
                      window.location.href = buildRevealHref(targetType, targetId)
                    }}
                  />
                ))}

                {agentRun.nodeExecutions
                  .flatMap((n) => n.toolCalls)
                  .map((t) => (
                    <ToolCallPanel
                      key={t.id}
                      toolCall={t}
                      onRequestReveal={(targetType, targetId) => {
                        window.location.href = buildRevealHref(targetType, targetId)
                      }}
                    />
                  ))}

                {agentRun.nodeExecutions
                  .flatMap((n) => n.llmCalls)
                  .map((c) => (
                    <LLMCallPanel
                      key={c.id}
                      llmCall={c}
                      onRequestReveal={(targetType, targetId) => {
                        window.location.href = buildRevealHref(targetType, targetId)
                      }}
                    />
                  ))}
              </section>

              <section
                className="ac-log-detail-drawer__section ac-log-detail-drawer__section--sensitive"
                data-testid="log-detail-sensitive"
              >
                <h3>sensitive payload (masked)</h3>
                <ul>
                  <li data-testid="masked-raw-prompt">
                    raw_prompt — {MASKED_LABEL}
                  </li>
                  <li data-testid="masked-raw-model-output">
                    raw_model_output — {MASKED_LABEL}
                  </li>
                  <li data-testid="masked-raw-input">
                    raw_input — {MASKED_LABEL}
                  </li>
                  <li data-testid="masked-raw-output">
                    raw_output — {MASKED_LABEL}
                  </li>
                  <li data-testid="masked-redaction-token">
                    redaction_token — {MASKED_LABEL}
                  </li>
                </ul>
                <a
                  href={buildRevealHref('agent_run', agentRun.id)}
                  className="ac-btn ac-btn--ghost"
                  data-testid="log-detail-request-reveal"
                  onClick={(e) => {
                    // Fallback: navigate even when React Router tries to
                    // intercept. The href is the shareable URL.
                    if (!e.metaKey && !e.ctrlKey) return
                  }}
                >
                  Request Reveal → Governance
                </a>
              </section>
            </>
          ) : (
            <div
              className="ac-log-detail-drawer__loading"
              data-testid="log-detail-loading"
            >
              {agentRunQuery.isLoading ? '加载 agent run…' : '无可关联 agent run'}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}

export default LogDetailDrawer
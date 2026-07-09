# REQ-035 Research

## Sources Consulted

- LangSmith observability documentation: <https://docs.langchain.com/langsmith/observability>
- Langfuse tracing documentation: <https://langfuse.com/docs/tracing>
- Arize Phoenix tracing documentation: <https://arize.com/docs/phoenix/tracing>
- OpenTelemetry GenAI semantic conventions: <https://opentelemetry.io/docs/specs/semconv/gen-ai/>
- OpenAI API key safety guidance: <https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety>

These sources converge on a trace-first model: traces contain nested spans or
observations for agent/workflow steps, LLM calls, tools, retrieval, scores/evals,
token/cost/latency, metadata, and user feedback. REQ-035 uses that model while
keeping InterCraft's internal records as the canonical source for the first MVP.

## Decision: Admin Console Boundary

**Decision**: Build a separate admin frontend entry within the current Vite
project, mounted at the unlinked `/admin-console` relative path for local
development and backed by `/api/v1/admin-console` and
`/api/v1/admin-console/observability` backend namespaces.

**Rationale**: The user now accepts the same host/port as long as the management
backend is hidden behind a dedicated relative path and no ordinary product page
links to it. A separate Vite entry keeps the admin UI isolated from the
user-facing route tree while reusing TypeScript, TanStack Query, Vitest,
Playwright, and shared design tokens. A separate backend process is unnecessary
for the MVP because access control, audit, API namespacing, and the admin path
tree isolate backend behavior without adding deployment complexity.

**Alternatives considered**:

- Add an advertised `/admin` route to the existing product frontend. Rejected
  because it would mix admin navigation into the ordinary product route tree and
  increase accidental exposure.
- Create a second repository/app. Rejected because it duplicates tooling and
  slows iteration.
- Run a separate backend admin service. Deferred because the first MVP needs
  internal visibility and debugging, not independent scaling.

## Decision: Canonical Trace And Payload Store

**Decision**: Use internal PostgreSQL records for trace metadata, spans, payload
metadata, LLM calls, eval links, and audit. Continue using OpenTelemetry spans
for runtime correlation and optional export, but do not make OTel or LangSmith
the first-release source of truth for the admin console.

**Rationale**: REQ-035 needs searchable user/business/agent/node/LLM/eval
drilldown with product-specific privacy, retention, and role enforcement.
Internal records make retention, masked raw access, coverage reports, and
dashboard snapshots deterministic. OTel remains the semantic and export layer,
matching the existing `backend/app/observability/tracing.py` foundation.

**Alternatives considered**:

- Store everything only in OTel backend. Rejected because retention and masked
  raw access are product-specific and must be enforced consistently.
- Store everything only in LangSmith. Rejected because LangSmith sync is out of
  scope and should remain optional.
- Use files for trace payloads. Rejected for production because querying,
  retention, and audit are harder to enforce.

## Decision: Payload Storage Shape

**Decision**: Store trace/span searchable metadata separately from payload
records. Payload records carry visibility class, redaction status, structured
payload shape, redacted summary, optional masked raw payload, content hash,
retention expiry, and audit links.

**Rationale**: Node/LLM payloads can be large and sensitive. Separating them
keeps list/search APIs fast, makes retention and reveal auditing explicit, and
prevents PM dashboard queries from touching raw-like content.

**Alternatives considered**:

- Put all payload content on the span row. Rejected because span search would
  become heavy and privacy boundaries would blur.
- External object store in MVP. Deferred because no object storage is currently
  part of the stack and PostgreSQL JSONB is enough for the Strong Debug MVP.

## Decision: Production Visibility Policy

**Decision**: Production is redacted by default plus approved masked raw. Default
views show metadata, redacted summaries, and structured payload shape. Approved
developer/reviewer roles may reveal masked raw after entering a reason; every
reveal creates an audit event.

**Rationale**: This implements the clarified requirement while avoiding
unrestricted admin raw browsing. It preserves enough structure for debugging
prompt shape, field presence, schema failures, tool arguments, and provider
errors without default exposure of raw business text.

**Alternatives considered**:

- No production raw. Rejected by the user because Strong Debug MVP needs deeper
  debugging than aggregate/redacted-only views.
- Break-glass approval workflow. Deferred because the user chose role-only
  access for MVP.
- Full raw for admins. Rejected by the spec because it conflicts with privacy
  and secret-safety requirements.

## Decision: cURL Reconstruction

**Decision**: Reconstruct cURL on demand from normalized request metadata,
redacted headers, endpoint, method, provider, model, body shape, and masked or
redacted request body depending on visibility mode. Never store or display a
literal secret-bearing cURL command.

**Rationale**: cURL is a debugging view, not a persistence format. On-demand
reconstruction lets the system inject placeholders such as `$OPENAI_API_KEY`,
remove cookies and bearer tokens, and include trace id/provider/model/attempt
metadata safely.

**Alternatives considered**:

- Store raw HTTP logs. Rejected because secrets and user content are too easy to
  leak.
- Store only provider request id. Rejected because it is insufficient for local
  reproduction and prompt/debug analysis.

## Decision: Retention And Freshness

**Decision**: Implement debug-heavy retention: PM metrics for 180 days,
redacted traces for 60 days, masked raw payloads for 14 days, and dashboard
snapshot freshness within 15 minutes of source data availability.

**Rationale**: The user selected this option to favor debugging depth. Retention
must be visible in settings, enforced by purge jobs/CLI, and validated by tests.
Dashboard APIs must show stale status when the 15-minute target is missed.

**Alternatives considered**:

- Balanced MVP (90/30/7 days, 1-hour refresh). Rejected by user in favor of
  stronger debugging.
- Long retention (365/90/30 days, near-real-time). Rejected for MVP because
  storage and privacy costs rise sharply.

## Decision: Role And Capability Model

**Decision**: Use an admin-console access dependency backed by explicit
capabilities. Existing `users.role` can gate broad internal roles, while an
admin-console grant record provides concrete capabilities such as
`PM_DASHBOARD_VIEW`, `TRACE_VIEW`, `MASKED_RAW_VIEW`, `EVAL_VIEW`, and
`SNAPSHOT_EXPORT`. The MVP may seed grants manually or by CLI; role-management
UI remains out of scope.

**Rationale**: The existing `User.role` is a single string and is enough for
simple admin checks, but masked raw and PM dashboard access need separate
capabilities. A grant table avoids building full role management while keeping
tests precise.

**Alternatives considered**:

- Only `users.role`. Rejected because one role string cannot represent PM-only,
  developer/reviewer masked-raw, and owner review cleanly.
- Full RBAC UI. Deferred because mutation-heavy admin management is out of
  scope.

## Decision: Coverage-Gap Reporting

**Decision**: Strong Debug MVP covers all production flows through centralized
Agent/LLM invocation entry points. The system must generate a coverage-gap
report listing legacy or bypassing flows outside those entry points.

**Rationale**: The clarified scope avoids an impossible "all code paths" claim
while still delivering broad coverage where instrumentation can be centralized.
Coverage gaps become visible work items rather than silent blind spots.

**Alternatives considered**:

- Priority flows only. Rejected because the user wants broad centralized
  observability.
- All product flows including non-AI CRUD. Rejected because it would turn this
  feature into a full product analytics rewrite.

## Decision: Eval Center Integration

**Decision**: Reuse existing `backend/app/eval` and REQ-033 eval artifacts as
the source for eval runs, cases, scores, reports, badcase links, and gate
status. Add read-only admin APIs to query them and link them to trace/span/LLM
records.

**Rationale**: REQ-033 already provides eval runner/report/badcase foundations.
REQ-035 should make those visible and trace-linked, not duplicate the runner.

**Alternatives considered**:

- Build a new eval runner. Rejected as duplication.
- Wait for LangSmith. Rejected because LangSmith sync is deferred.

## Decision: Dashboard Snapshot Format

**Decision**: Store dashboard snapshots as privacy-safe aggregate artifacts with
filters, generated_at, metric values, metric definitions/references, freshness
state, warnings, and creator audit metadata. Export formats can be JSON and
Markdown for MVP.

**Rationale**: JSON supports tests and downstream automation; Markdown supports
quick PM/owner sharing without building a full reporting designer.

**Alternatives considered**:

- PDF/PPT reports in first release. Deferred because the Strong Debug MVP is
  already broad and snapshot content correctness matters first.

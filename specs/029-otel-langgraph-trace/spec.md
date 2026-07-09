# Feature Specification: OpenTelemetry & LangGraph Distributed Trace

**Feature Branch**: `[029-otel-langgraph-trace]`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "替换 prometheus+structlog+ContextVar 拼凑，5 个 graph 节点串成一次 trace，跨 LLM 调用 span，OTLP export。"

## User Scenarios & Testing

### User Story 1 - One Distributed Trace Per Agent Invocation (Priority: P1)

As an on-call maintainer, when a user reports that an interview produced a strange result, I want to retrieve a single distributed trace that spans the entire invocation — every graph node entry/exit, every LLM call, every tool call — so I can see exactly where time was spent, which call failed, and what the inputs/outputs were at each step, without reconstructing from scattered logs.

**Why this priority**: This is the core debugging value. Today, an interview invocation touches 5+ graph nodes, multiple LLM calls, and tool calls, all logged via `structlog` + `_request_id_var` ContextVar. Reconstructing the causal chain requires grepping logs by request_id across processes. A single distributed trace makes the chain queryable as one unit. P1 because production debugging is the highest-leverage observability win.

**Independent Test**: Can be fully tested by triggering one interview session, then querying the trace backend by the user's thread id, and confirming the returned trace contains ≥5 node spans, ≥5 LLM call spans, and any tool call spans, all under one trace id.

**Acceptance Scenarios**:

1. **Given** a user completes a 5-question interview, **When** the on-call queries the trace backend by thread id, **Then** one trace is returned containing one span per graph node (intake, planner, interviewer×5, score×5, report).
2. **Given** the trace is open, **When** the on-call expands an LLM call span, **Then** the span shows model, input token count, output token count, latency, and cache status.
3. **Given** the trace is open, **When** the on-call expands a tool call span, **Then** the span shows tool name, arguments summary, return value summary, and duration.
4. **Given** a node failed mid-invocation, **When** the on-call views the trace, **Then** the failing span is marked with an error status and the error message is visible.

---

### User Story 2 - Trace Context Propagates Across Process Boundaries (Priority: P2)

As a maintainer, the trace context (trace id, span id) must propagate across the HTTP request → WebSocket frame → ARQ worker task → LLM call → graph node boundaries, so that a single user invocation produces a single contiguous trace rather than fragmented pieces.

**Why this priority**: Without cross-process propagation, US1's "single trace" is a lie — each process boundary starts a new trace. P2 because it is the engineering work that makes US1 real; it's not user-visible value on its own but it's the substrate.

**Independent Test**: Can be fully tested by triggering an agent invocation that crosses HTTP → WS → ARQ, then confirming the trace id is identical across all spans in the backend.

**Acceptance Scenarios**:

1. **Given** an HTTP request starts an agent invocation, **When** the invocation crosses into an ARQ worker (e.g., ability_diagnose trigger), **Then** the ARQ task carries the same trace id.
2. **Given** a WebSocket frame triggers a graph node, **When** the node runs, **Then** the node span has the same trace id as the originating HTTP request.
3. **Given** the interview graph invokes the planner subgraph, **When** the subgraph runs, **Then** the subgraph's spans are nested under the parent graph's span (same trace id).
4. **Given** trace context is lost across a boundary (bug), **When** the next span starts, **Then** a warning is logged and a new trace is started (fail-open, not fail-closed).

---

### User Story 3 - Traces Export To A Queryable Backend (Priority: P2)

As a maintainer, I want traces exported via OTLP to a configurable backend (self-hosted or managed), so that I can query, visualize, and retain traces in a central place accessible to the on-call team.

**Why this priority**: Export is how traces become useful. P2 because it's the delivery mechanism for US1; without it traces exist in-memory only.

**Independent Test**: Can be fully tested by running one agent invocation, then querying the configured backend, and confirming the trace is retrievable.

**Acceptance Scenarios**:

1. **Given** the backend endpoint is configured, **When** an agent invocation completes, **Then** the trace is exported via OTLP within 5 seconds.
2. **Given** the backend is unavailable, **When** export is attempted, **Then** the system fails open — traces are buffered or dropped, agent execution is unaffected.
3. **Given** a development environment, **When** no external backend is configured, **Then** a local trace viewer is available for inspection without external dependencies.
4. **Given** the backend retention policy expires traces after N days, **When** the on-call queries an expired trace, **Then** a clear "expired" response is returned.

---

### User Story 4 - Logs And Metrics Join To Traces (Priority: P3)

As a maintainer, I want structured logs and prometheus metrics to carry the trace id, so that when I find a suspicious log entry or metric spike, I can jump directly to the corresponding trace for full context.

**Why this priority**: Joinable observability is the multiplier — logs, metrics, and traces each tell part of the story; together they tell the whole story. P3 because the existing logs and metrics work; this feature just adds the join key.

**Independent Test**: Can be fully tested by triggering one agent invocation, finding a log entry for that invocation, and confirming the log's trace id matches the trace in the backend.

**Acceptance Scenarios**:

1. **Given** a structured log entry is emitted during an agent invocation, **When** the maintainer reads the log, **Then** it includes trace id and span id fields.
2. **Given** a prometheus metric is incremented during an agent invocation, **When** the maintainer views the metric, **Then** it carries the trace id as an exemplar (or equivalent correlation).
3. **Given** the maintainer has a trace id from the trace backend, **When** they grep logs by that trace id, **Then** all log entries for that invocation are returned.
4. **Given** the legacy request_id approach still exists during migration, **When** a request has both, **Then** the trace id supersedes request_id as the primary correlation key.

---

### Edge Cases

- What happens when the OTel backend is unavailable? → Fail-open: traces are buffered (bounded queue) or dropped, agent execution is never blocked.
- What happens when trace context is lost across a process boundary (bug)? → A new trace is started for the orphaned span; a warning is logged; the spans are still individually queryable.
- What happens when sampling drops an error trace? → Errors are 100% sampled by default; no error trace is dropped.
- What happens when PII appears in a span attribute? → Redaction layer strips it before export; the span is retained with the PII removed.
- What happens during a very long agent invocation (10+ minutes)? → Spans are exported as they complete (streaming); the full trace is visible during execution, not only at the end.
- What happens during concurrent agent invocations? → Each has its own trace id; no cross-contamination; the backend can filter by trace id.
- What happens when the local dev trace viewer is used without a backend? → Traces are kept in-memory and viewable; the viewer does not require external dependencies.

## Requirements

### Functional Requirements

**Trace emission**

- **FR-001**: System MUST emit one distributed trace per agent invocation, spanning all 5 graph nodes, all LLM calls, and all tool calls.
- **FR-002**: Each graph node MUST be a span with start time, end time, node name, and a state delta summary.
- **FR-003**: Each LLM call MUST be a child span with model, input token count, output token count, latency, and cache status (links to feature 027).
- **FR-004**: Each tool call MUST be a child span with tool name, arguments summary, return value summary, and duration.
- **FR-005**: Spans MUST be hierarchically nested — LLM and tool spans are children of the node span that invoked them.

**Context propagation**

- **FR-006**: Trace context MUST propagate across HTTP request → WebSocket frame → ARQ worker task → LLM call → graph node boundaries.
- **FR-007**: Trace context MUST propagate across the planner subgraph boundary in the interview graph (parent → subgraph).
- **FR-008**: The existing request_id ContextVar MUST be migrated to OpenTelemetry trace context, with a backward-compatible shim during transition.

**Export and querying**

- **FR-009**: System MUST export traces via OTLP to a configurable backend.
- **FR-010**: Traces MUST be queryable by user id, thread id, graph name, node name, time range, and outcome.
- **FR-011**: Trace sampling MUST be configurable (e.g., 100% for errors, 10% for success) and overridable per invocation.
- **FR-012**: System MUST expose a local trace viewer for development that requires no external backend.

**Integration with existing observability**

- **FR-013**: Structured logs MUST carry the trace id and span id so logs join to traces.
- **FR-014**: Prometheus metrics MUST correlate to traces via exemplars (or equivalent mechanism).
- **FR-015**: The existing prometheus_client and structlog integrations MUST be retained (augmented, not replaced).

**Safety and testing**

- **FR-016**: System MUST redact PII from span attributes before export.
- **FR-017**: Trace export failure MUST NOT break agent execution (fail-open).
- **FR-018**: The deterministic mock LLM client MUST emit spans so traces are testable without the real provider.
- **FR-019**: The eval suite (feature 026) MUST include a case verifying that trace context propagates end-to-end.

### Key Entities

- **Trace**: id, root span, user id, thread id, graph, start, end, outcome, sampling decision.
- **Span**: id, parent id, trace id, name (node/llm/tool), start, end, attributes (redacted), status, kind.
- **TraceExportConfig**: backend endpoint, protocol (OTLP), sampling rules, headers, retention policy.
- **TraceContextCarrier**: the propagated context (trace id, span id, trace flags) across process boundaries.

## Success Criteria

### Measurable Outcomes

- **SC-001**: One interview agent invocation produces a single trace containing ≥5 node spans and ≥5 LLM call spans.
- **SC-002**: Trace context propagates across HTTP → WS → ARQ with the same trace id in ≥99% of invocations.
- **SC-003**: Structured log entries carry the trace id in ≥99% of cases, enabling log-to-trace joins.
- **SC-004**: Trace export overhead adds ≤5% to total agent invocation latency.
- **SC-005**: PII is redacted from span attributes in 100% of exported spans (verified by sampling audit).
- **SC-006**: Local dev trace viewer works without an external backend configured.
- **SC-007**: Default sampling reduces export volume by ≥80% while retaining 100% of error traces.
- **SC-008**: Maintainer-reported time-to-diagnose on production agent incidents is reduced by ≥50% versus the pre-feature baseline (scattered-log debugging).

## Assumptions

- OTLP is the export protocol; the specific backend (Jaeger, Tempo, managed SaaS) is decided in planning.
- OpenTelemetry Python SDK is the integration point; no custom trace framework is built.
- The existing prometheus_client and structlog are retained (augmented, not replaced).
- The request_id ContextVar migration is backward-compatible during transition; legacy code continues to work.
- Frontend is not modified in this feature.
- Constitution Principle V (Observability) is the primary principle served — this feature directly extends the existing metric/log/request_id infrastructure with traces.
- Constitution Principle IV (Integration & Synchronization Testing): cross-process propagation is verified by integration tests, not unit-only.
- The local dev trace viewer is a developer convenience, not a production backend.
- Sampling rules are configurable at runtime (env var or config), not hard-coded.
- This feature complements feature 026 (eval loop) — traces produced during eval runs are also available for debugging test failures.

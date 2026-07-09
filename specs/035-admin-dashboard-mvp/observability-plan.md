# REQ-035 Detailed Observability And Eval Dashboard Plan

## Positioning

REQ-035 is not only a PM aggregate dashboard. It should become the first version
of an internal AI observability workbench:

- PMs use it to understand product usage, funnel conversion, AI cost, badcases,
  and release quality.
- The owner uses it to generate trustworthy review snapshots and inspect risk.
- Developers and agent maintainers use it to debug a single user flow down to
  agent nodes, tool calls, LLM requests, responses, retries, and evaluator runs.

This makes REQ-035 the internal console layer that sits before LangSmith sync and
production-grade external trace export.

## Industry Reference Baseline

Mature LLM observability products converge on the same primitives:

- **Trace-first debugging**: LangSmith positions observability as visibility from
  individual traces to production metrics, with trace filtering, sharing,
  comparison, dashboards, alerts, and automations.
- **Traces, sessions, observations**: Langfuse models LLM apps around traces,
  sessions, and nested observations. It records prompts, responses, token usage,
  latency, tool calls, retrieval steps, metadata, scores, datasets, experiments,
  and custom dashboards.
- **OpenTelemetry compatibility**: Phoenix and OpenTelemetry GenAI conventions
  treat LLM, retrieval, tool, memory, workflow, and agent operations as spans,
  metrics, and events. This is the best long-term vendor-neutral foundation.
- **Evaluator transparency**: Phoenix traces evaluator runs, including evaluator
  input, judge prompt, score, and timing. LangSmith and Langfuse both support
  offline datasets, online evaluation, human review, code evaluators,
  LLM-as-judge, pairwise comparison, and regression testing.

The practical takeaway: build the internal data model around trace/span identity
and expose dashboards as filtered views of the same canonical event stream.

## Core Drilldown Model

Use one correlation chain across all admin views:

```text
User
  -> Business Session / Business Run
    -> Workflow Run / Agent Run
      -> Agent Node Span
        -> Action Span
          -> LLM Call / Tool Call / Retrieval / Memory / Evaluator Call
            -> Provider HTTP Attempt / Streaming Chunk / Error
```

Minimum stable identifiers:

| Level | Stable ID | Purpose |
|---|---|---|
| User | `user_id` / anonymized display id | User-level filtering and support review. |
| Business | `business_run_id`, `session_id`, `feature_area` | Single resume diagnosis, interview, error coach, job flow, etc. |
| Trace | `trace_id`, `span_id`, `parent_span_id` | Cross-service causal graph. |
| Agent | `agent_run_id`, `agent_name`, `agent_version` | Compare agent behavior across versions. |
| Node | `node_name`, `node_run_id`, `node_attempt` | Inspect every LangGraph node. |
| LLM | `llm_call_id`, `provider_request_id`, `attempt` | Debug provider calls, retries, and cost. |
| Eval | `eval_run_id`, `dataset_id`, `case_id`, `evaluator_id` | Reproduce and compare eval outcomes. |
| Version | `source_revision`, `prompt_version`, `rubric_version`, `model`, `experiment_id` | Tie behavior to code and prompt changes. |

## Admin Console Pages

### 1. Admin Home

- Health summary: active users, AI calls, failed AI calls, open badcases, latest
  eval gate status, stale data warnings.
- Quick links: Product Dashboard, Trace Explorer, Eval Center, Badcase Review,
  Privacy Audit.
- Strict role display: current role, environment, data visibility mode.

### 2. Product Data Dashboard

Purpose: PM review and reporting.

Metric groups:

- User and traffic: UV, registrations, active users, returning users, cohort
  retention if available.
- Core funnel: entry/login -> resume create/upload -> diagnosis -> report view
  -> suggestion acceptance -> interview start -> interview completion ->
  feedback view.
- Resume center: diagnosis volume, issue categories, score delta, suggestion
  acceptance, export/share actions.
- Ability and interview: interview starts, completions, dropout points, score
  distribution, feedback view rate.
- AI operations: calls, success/failure, p50/p95 latency, streaming first-token
  delay, input/output/cache/reasoning tokens, cost estimate, model split.
- Feedback and badcase: count, category, severity, status, owner/reviewer,
  promotion readiness.
- Version and experiment: code revision, prompt version, rubric version, model,
  experiment, eval baseline.

Required UX:

- Date range, environment, feature area, agent, model, prompt version filters.
- Metric definitions and freshness on every section.
- Valid zero, missing data, partial data, stale data, and failure states.
- Snapshot export for PM/owner review with aggregate/redacted data only.

### 3. Trace Explorer

Purpose: find and compare exact user/business/agent runs.

Filters:

- `user_id`, anonymized user label, business run, trace id, session id.
- Feature area, agent, node, model, prompt version, status, error type.
- Token range, cost range, latency range, date range, environment.
- Eval score range, badcase status, feedback category.

List columns:

- Time, user, business type, trace id, agent, status, duration, LLM calls,
  tokens, cost, eval score, badcase flag, version.

Trace detail:

- Timeline waterfall.
- Span tree with parent/child nesting.
- Error and retry markers.
- Search within trace payloads in allowed visibility mode.
- Compare two traces side by side by version, model, prompt, or user segment.

### 4. Agent Run Detail

Purpose: inspect one agent run as a graph execution.

Required detail:

- Agent identity: name, version, source revision, graph name, entrypoint.
- Inputs: business input summary, selected visibility mode, raw input when
  allowed.
- Node timeline: node name, start/end, duration, status, retries, interrupt
  state, checkpoint id.
- Node I/O: state before, node input, node output, state diff, emitted events,
  next-node decision, guardrail decision.
- Tool/retrieval/memory subspans: arguments, result summary, result payload when
  allowed, matched docs and scores, memory ids touched.
- Final output and handoff context.

### 5. LLM Call Detail

Purpose: debug a single model invocation.

Record and display:

- Provider, base URL, endpoint, method, model requested, model returned.
- Request params: temperature, top_p, max tokens, seed, stop sequences, output
  type, stream flag, tools, response format.
- Prompt context: system instructions, prompt template name/version, variables,
  input messages, compacted-context indicator.
- Response: output messages, finish reason, refusal/safety fields if present,
  structured output validation result, provider request id.
- Usage: input/output/cache/reasoning tokens, estimated cost, latency,
  time-to-first-token/chunk, streaming chunk count.
- Retries: attempt number, retry delay, error type, HTTP status, rate-limit info.
- Raw HTTP view:
  - Canonical method, URL, headers, body, and response metadata.
  - A generated cURL command for reproduction.
  - All secrets redacted by default: `Authorization`, API keys, cookies,
    organization/project tokens, internal service tokens.
  - Optional replay command may use environment placeholders such as
    `$OPENAI_API_KEY`, never a stored secret value.

### 6. Eval Center

Purpose: connect quality metrics to traces and releases.

Views:

- Eval run list: dataset, revision, prompt/rubric/model, pass rate, average
  score, failed cases, cost, runtime.
- Case detail: input, expected behavior, actual output, evaluator results,
  related trace, badcase link, owner decision.
- Evaluator detail: type, rubric, judge prompt/version, score distribution,
  disagreement with human review, drift over time.
- Regression gate: latest PR/CI eval status, threshold failures, approved
  overrides, dual-approval record.

Eval metrics:

- Task success/pass rate.
- Rubric score and per-dimension scores.
- Format/schema validity.
- Safety/PII leakage.
- Hallucination or unsupported claim rate where applicable.
- Retrieval relevance/groundedness when retrieval exists.
- Tool-call correctness and tool-call failure rate.
- Human agreement and reviewer disagreement rate.
- Stability across repeated runs.
- Cost, token, latency, and timeout rate.
- Regression delta against baseline.

### 7. Badcase And Golden Case Review

- Badcase queue by severity, feature, agent, node, model, and eval score.
- Link each badcase to trace, node, LLM call, feedback, and current owner.
- Promote selected badcases to golden-case candidates.
- Preserve approval and closure history.
- MVP can keep mutation minimal, but the read path must be visible from the
  admin console.

### 8. Privacy And Data Quality Audit

- Visibility mode: aggregate, redacted, masked raw, approved raw.
- Source completeness by data source and section.
- Retention status and upcoming purge count.
- Admin access log and raw-view audit.
- Redaction test evidence and sensitive-field detection failures.

## Logging Granularity

### Always Record

- Trace/span hierarchy, timestamps, duration, status, error type.
- User/business/session correlation identifiers.
- Agent/node/tool/model names and versions.
- Token usage, cost estimate, latency, retry count.
- Prompt/rubric/model/source revision identifiers.
- Data visibility classification and retention class.

### Record When Allowed By Environment And Policy

- Node input, output, and state diff.
- Prompt variables and input/output messages.
- Tool arguments and tool responses.
- Retrieved document text snippets and scores.
- Evaluator input, judge prompt, score rationale, and final score.
- Raw provider request body and response body.

### Never Store Or Display As Raw Values

- API keys, bearer tokens, cookies, session tokens, private keys.
- Full Authorization headers.
- Credentials embedded in URLs.
- Internal service credentials.

## Visibility Modes

| Mode | Audience | Content | Use Case |
|---|---|---|---|
| Aggregate | PM/BOSS report | Metrics only | Reporting and review. |
| Redacted Trace | PM/owner/reviewer | Trace tree with sensitive text summarized or masked | Most admin debugging. |
| Masked Raw | Approved developer/reviewer | Raw-like payloads with secrets and detected PII masked | Debugging node and LLM behavior. |
| Approved Raw | Break-glass only | Sensitive business text may be visible, secrets still hidden | Local/staging reproduction or approved incident review. |

Production default should be aggregate or redacted trace. Approved raw access
requires role, reason, audit event, short retention, and explicit environment
policy.

## Data Architecture

### Write Path

1. Product request creates or receives `request_id` and `trace_id`.
2. Business workflow creates `business_run_id`.
3. Agent runner creates `agent_run_id`.
4. Each graph node emits a span with node input/output metadata according to
   visibility policy.
5. LLM client wrapper records provider request/response metadata, usage, errors,
   retries, and reconstructable cURL with redacted secrets.
6. Eval runner links eval results to traces, versions, datasets, and badcases.
7. Aggregator generates dashboard metric snapshots from canonical trace/event
   records.

### Storage Layers

- Trace/span tables for searchable metadata and hierarchy.
- Large payload object storage or payload table for raw/masked bodies, addressed
  by payload hash/id and governed by retention policy.
- Metric snapshots for dashboard performance.
- Eval results and badcase promotion records.
- Admin audit events for access, reveal, export, and snapshot generation.

### Retention Defaults

- Local/dev: full raw payloads allowed for short retention.
- CI: synthetic/golden payloads allowed; secrets always redacted.
- Staging: raw only for approved synthetic/golden/test data; otherwise masked.
- Production: aggregate and redacted trace by default; approved raw only through
  break-glass policy if later accepted.

## MVP Slices

### Slice A - Admin Shell And RBAC

- Separate admin entry point/port.
- Login/access denial/session expiry.
- Admin audit events.
- Empty dashboard shell.

### Slice B - Trace Schema And Capture

- Canonical trace/span/event schema.
- Correlation ids across user, business run, agent run, node, LLM call.
- LLM wrapper captures provider metadata, redacted cURL, tokens, cost, latency,
  retries, and request ids.

### Slice C - Trace Explorer

- Search/filter traces.
- Trace waterfall/tree.
- Agent run detail with node timeline.
- Node I/O in masked mode.
- LLM call detail with redacted cURL.

### Slice D - Product Dashboard MVP

- PM dashboard metrics from trace/event snapshots.
- Definitions, freshness, partial/stale/zero states.
- Snapshot export.

### Slice E - Eval Center

- Eval run list and case detail.
- Links from eval failures to traces, nodes, and badcases.
- Regression delta and gate status.

### Slice F - Privacy Hardening

- Visibility modes.
- Raw reveal audit and reason capture.
- Retention purge job/evidence.
- Privacy validation tests.

## Estimated Effort

| Delivery Level | Scope | Estimate |
|---|---|---|
| Debug MVP | Admin shell, trace schema, LLM metadata/cURL redacted view, trace explorer basics, dashboard reuse from REQ-033 | 5-8 focused dev days |
| Strong MVP | Adds node I/O, eval center, snapshots, privacy modes, audit, data freshness, tests/evidence | 2-3 weeks |
| Production-grade | Adds scale tuning, break-glass workflow, retention automation, advanced compare, alerting, external LangSmith sync | 4-6+ weeks |

## Main Risks

- Raw node/LLM payloads can contain resumes, job descriptions, interview answers,
  prompt secrets, or personal data. This is a product-security feature, not just
  a UI feature.
- Capturing every node input/output can create high storage volume and slow
  admin queries unless large payloads and metadata are stored separately.
- cURL reproduction is useful but dangerous if secrets are captured. It must be
  reconstructed with placeholders, not stored as a literal secret-bearing shell
  command.
- Production raw access may conflict with privacy policy. Treat it as deferred
  unless explicitly approved.
- Dashboard correctness depends on metric definitions and data freshness, not
  only frontend rendering.

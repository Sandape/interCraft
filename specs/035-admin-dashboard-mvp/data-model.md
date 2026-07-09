# REQ-035 Data Model

## Overview

REQ-035 adds admin-console and agent-observability records on top of existing
REQ-033 PM dashboard, badcase, eval, redaction, and retention records. The model
separates searchable metadata from sensitive payload content.

## Entities

### AdminAccessGrant

Represents a manually seeded or CLI-managed permission grant for the admin
console MVP.

| Field | Type | Required | Notes |
|---|---|---|---|
| `grant_id` | UUID | yes | Stable grant id. |
| `user_id` | UUID | yes | References `users.id`. |
| `role_label` | string | yes | `pm`, `owner`, `developer`, `reviewer`, `admin`. |
| `capability` | string | yes | `PM_DASHBOARD_VIEW`, `TRACE_VIEW`, `MASKED_RAW_VIEW`, `EVAL_VIEW`, `SNAPSHOT_EXPORT`, `PRIVACY_AUDIT_VIEW`. |
| `environment_scope` | string | yes | `local`, `ci`, `staging`, `production`, or `all`. |
| `status` | string | yes | `active`, `revoked`, `expired`. |
| `created_by` | UUID/null | no | Actor that granted access. |
| `created_at` | datetime | yes | Audit timestamp. |
| `expires_at` | datetime/null | no | Optional expiry. |

Validation:

- `MASKED_RAW_VIEW` in production is valid only for `developer` or `reviewer`
  role labels.
- Revoked or expired grants do not authorize access.

### AdminAuditEvent

Append-only record of protected admin activity.

| Field | Type | Required | Notes |
|---|---|---|---|
| `audit_id` | UUID | yes | Stable audit id. |
| `actor_id` | UUID/null | no | Null only for unauthenticated denial. |
| `action` | string | yes | Example: `admin.login`, `trace.view`, `payload.reveal`, `curl.view`, `snapshot.create`. |
| `target_type` | string | yes | `trace`, `span`, `payload`, `llm_call`, `eval_case`, `dashboard_snapshot`, `admin_console`. |
| `target_id` | string/null | no | Target identifier. |
| `reason` | string/null | required for reveal | Required for masked raw reveal and cURL view. |
| `visibility_mode` | string | yes | `aggregate`, `redacted_trace`, `masked_raw`, `approved_raw`. |
| `decision` | string | yes | `allowed`, `denied`. |
| `environment` | string | yes | Runtime environment. |
| `request_id` | string/null | no | HTTP request id. |
| `trace_id` | string/null | no | Current trace id if present. |
| `created_at` | datetime | yes | Append timestamp. |

Validation:

- `payload.reveal` and `curl.view` require non-empty `reason`.
- Audit events are append-only.

### ObservabilityTrace

Root searchable record for one business/agent execution chain.

| Field | Type | Required | Notes |
|---|---|---|---|
| `trace_id` | string | yes | 32-char OTel-compatible trace id or generated internal id. |
| `user_id` | UUID/null | no | May be null for production redaction policy. |
| `anonymized_user_label` | string/null | no | Stable non-PII display label. |
| `business_run_id` | string | yes | Resume diagnosis, interview, error coach, eval case, etc. |
| `session_id` | string/null | no | Business or auth session id where available. |
| `feature_area` | string | yes | `resume`, `interview`, `error_coach`, `eval`, etc. |
| `environment` | string | yes | local/ci/staging/production. |
| `status` | string | yes | `running`, `success`, `error`, `partial`, `expired`. |
| `started_at` | datetime | yes | Trace start. |
| `ended_at` | datetime/null | no | Trace end. |
| `duration_ms` | integer/null | no | Derived at close. |
| `source_revision` | string | yes | Code revision or `unknown`. |
| `prompt_version` | string | no | Where available. |
| `rubric_version` | string | no | Where available. |
| `model_set` | array/string | no | Models used. |
| `privacy_class` | string | yes | Highest sensitivity classification. |
| `retention_expires_at` | datetime | yes | Redacted trace expiry, 60 days in production. |

Relationships:

- Has many `ObservabilitySpan`.
- Has many `LLMCallRecord`.
- May link to `EvalRun`, `EvalCaseResult`, `Badcase`, and `DashboardSnapshot`.

### ObservabilitySpan

Timed unit of work inside a trace.

| Field | Type | Required | Notes |
|---|---|---|---|
| `span_id` | string | yes | Stable span id. |
| `trace_id` | string | yes | Parent trace. |
| `parent_span_id` | string/null | no | Null for root. |
| `span_kind` | string | yes | `business`, `agent_run`, `node`, `llm`, `tool`, `retrieval`, `memory`, `eval`. |
| `name` | string | yes | Human readable name. |
| `agent_name` | string/null | no | For agent/node spans. |
| `agent_version` | string/null | no | For agent/node spans. |
| `node_name` | string/null | no | For node spans. |
| `node_attempt` | integer/null | no | Retry attempt. |
| `status` | string | yes | `running`, `success`, `error`, `skipped`, `partial`. |
| `started_at` | datetime | yes | Span start. |
| `ended_at` | datetime/null | no | Span end. |
| `duration_ms` | integer/null | no | Derived. |
| `input_payload_id` | UUID/null | no | Payload record. |
| `output_payload_id` | UUID/null | no | Payload record. |
| `state_diff_payload_id` | UUID/null | no | Payload record. |
| `error_type` | string/null | no | Error class/category. |
| `error_message_summary` | string/null | no | Redacted summary. |
| `next_step` | string/null | no | Graph next-node decision. |

Validation:

- `span_kind=node` should include `node_name`.
- `span_kind=llm` should link to an `LLMCallRecord`.

### ObservabilityPayload

Sensitive or semi-sensitive payload linked to traces/spans/LLM calls.

| Field | Type | Required | Notes |
|---|---|---|---|
| `payload_id` | UUID | yes | Stable payload id. |
| `trace_id` | string | yes | Parent trace. |
| `span_id` | string/null | no | Parent span. |
| `payload_kind` | string | yes | `node_input`, `node_output`, `state_diff`, `llm_request`, `llm_response`, `tool_args`, `tool_result`, `eval_input`, `eval_output`. |
| `visibility_mode` | string | yes | `aggregate`, `redacted_trace`, `masked_raw`, `approved_raw`. |
| `privacy_class` | string | yes | `public_metadata`, `internal`, `sensitive_user_content`, `secret`. |
| `redaction_status` | string | yes | `not_required`, `redacted`, `masked`, `blocked`, `failed`. |
| `shape_json` | JSON | yes | Field names/types/array sizes, no secrets. |
| `redacted_summary` | text/null | no | Safe summary. |
| `masked_raw_json` | JSON/null | no | Masked body, available only when policy permits. |
| `content_hash` | string | yes | Hash for dedup/debug. |
| `retention_expires_at` | datetime | yes | 14 days for production masked raw. |
| `created_at` | datetime | yes | Capture time. |

Validation:

- `masked_raw_json` must not contain API keys, bearer tokens, cookies, private
  credentials, or known PII fields.
- Production full raw payloads are not stored in the MVP.

### LLMCallRecord

One model-provider invocation attempt or logical call.

| Field | Type | Required | Notes |
|---|---|---|---|
| `llm_call_id` | UUID | yes | Stable id. |
| `trace_id` | string | yes | Parent trace. |
| `span_id` | string | yes | LLM span. |
| `provider` | string | yes | OpenAI-compatible provider name. |
| `base_url` | string | yes | Redacted URL, no credentials. |
| `endpoint` | string | yes | API path. |
| `http_method` | string | yes | Usually POST. |
| `model_requested` | string | yes | Requested model. |
| `model_returned` | string/null | no | Provider-returned model if present. |
| `request_payload_id` | UUID/null | no | Linked payload. |
| `response_payload_id` | UUID/null | no | Linked payload. |
| `parameters_json` | JSON | yes | temperature, max tokens, response format, tools, stream flag, etc. |
| `provider_request_id` | string/null | no | Provider id. |
| `attempt` | integer | yes | Retry attempt number. |
| `status` | string | yes | `success`, `error`, `timeout`, `rate_limited`, `partial_stream`. |
| `http_status` | integer/null | no | HTTP response code. |
| `finish_reason` | string/null | no | Provider finish reason. |
| `prompt_tokens` | integer | yes | 0 if unavailable. |
| `completion_tokens` | integer | yes | 0 if unavailable. |
| `cache_tokens` | integer | yes | 0 if unavailable. |
| `reasoning_tokens` | integer | yes | 0 if unavailable. |
| `estimated_cost` | decimal/null | no | Estimate, not billing ledger. |
| `latency_ms` | integer/null | no | Total latency. |
| `time_to_first_token_ms` | integer/null | no | Streaming only. |
| `stream_chunk_count` | integer/null | no | Streaming only. |
| `error_type` | string/null | no | Error class/category. |
| `error_summary` | string/null | no | Redacted summary. |
| `created_at` | datetime | yes | Attempt start. |

Validation:

- Secret-bearing headers are never stored.
- cURL view is reconstructed, not persisted as a raw command.

### ToolOperationRecord

Tool, retrieval, or memory operation invoked by an agent node.

| Field | Type | Required | Notes |
|---|---|---|---|
| `operation_id` | UUID | yes | Stable id. |
| `trace_id` | string | yes | Parent trace. |
| `span_id` | string | yes | Parent span. |
| `operation_type` | string | yes | `tool`, `retrieval`, `memory`. |
| `name` | string | yes | Tool/retriever/memory name. |
| `input_payload_id` | UUID/null | no | Arguments/query. |
| `output_payload_id` | UUID/null | no | Result. |
| `score_json` | JSON/null | no | Retrieval scores or confidence. |
| `status` | string | yes | success/error/partial. |
| `duration_ms` | integer/null | no | Timing. |

### EvalRun

Read model for eval execution visible in the Eval Center. May map to existing
REQ-033 eval report records.

| Field | Type | Required | Notes |
|---|---|---|---|
| `eval_run_id` | UUID/string | yes | Stable eval run id. |
| `suite` | string | yes | `golden`, `nightly`, etc. |
| `environment` | string | yes | ci/staging/local. |
| `dataset_id` | string | yes | Dataset/schema id. |
| `source_revision` | string | yes | Code revision. |
| `prompt_version` | string/null | no | Prompt context. |
| `rubric_version` | string/null | no | Rubric context. |
| `model` | string/null | no | Judge or model under test. |
| `status` | string | yes | `passed`, `failed`, `incomplete`, `overridden`. |
| `pass_rate` | float | yes | 0..1. |
| `avg_score` | float/null | no | Aggregate score. |
| `total_tokens` | integer | yes | Eval token estimate. |
| `estimated_cost` | decimal/null | no | Eval cost estimate. |
| `started_at` | datetime | yes | Start. |
| `completed_at` | datetime/null | no | End. |

### EvalCaseResult

One evaluated case.

| Field | Type | Required | Notes |
|---|---|---|---|
| `case_result_id` | UUID | yes | Stable id. |
| `eval_run_id` | UUID/string | yes | Parent run. |
| `case_id` | string | yes | Golden/badcase id. |
| `trace_id` | string/null | no | Related trace. |
| `llm_call_id` | UUID/null | no | Related model call. |
| `badcase_id` | UUID/null | no | Related badcase. |
| `status` | string | yes | pass/fail/incomplete. |
| `score` | float/null | no | Overall score. |
| `score_dimensions_json` | JSON | yes | Rubric dimensions. |
| `failure_reason` | string/null | no | Redacted reason. |

### DashboardMetricSnapshot

Extends existing REQ-033 metric snapshot semantics.

| Field | Type | Required | Notes |
|---|---|---|---|
| `snapshot_id` | UUID | yes | Stable id. |
| `metric_id` | string | yes | Metric catalog id. |
| `period_start` | datetime | yes | Filter period start. |
| `period_end` | datetime | yes | Filter period end. |
| `value` | float | yes | Metric value. |
| `unit` | string | yes | count/percent/ms/tokens/currency. |
| `dimensions_json` | JSON | yes | env, feature, agent, model, prompt, etc. |
| `definition_version` | string | yes | Metric definition version. |
| `freshness_at` | datetime | yes | Source freshness. |
| `quality_state` | string | yes | `complete`, `partial`, `empty`, `stale`, `error`. |
| `retention_expires_at` | datetime | yes | 180 days in production. |

### DashboardSnapshot

Shareable, privacy-safe dashboard report.

| Field | Type | Required | Notes |
|---|---|---|---|
| `dashboard_snapshot_id` | UUID | yes | Stable id. |
| `created_by` | UUID | yes | Actor. |
| `created_at` | datetime | yes | Generation time. |
| `filters_json` | JSON | yes | Date range, environment, feature, model, etc. |
| `metrics_json` | JSON | yes | Aggregate/redacted metric values. |
| `warnings_json` | JSON | yes | Stale/partial/privacy warnings. |
| `format` | string | yes | `json`, `markdown`. |
| `privacy_status` | string | yes | Must be `safe` to export. |

### ObservabilityCoverageGap

Record produced by coverage reporting.

| Field | Type | Required | Notes |
|---|---|---|---|
| `gap_id` | UUID | yes | Stable id. |
| `feature_area` | string | yes | Product area. |
| `flow_name` | string | yes | Flow outside centralized instrumentation. |
| `reason` | string | yes | `legacy_path`, `direct_provider_call`, `missing_node_wrapper`, `unknown`. |
| `severity` | string | yes | `low`, `medium`, `high`. |
| `detected_at` | datetime | yes | Detection time. |
| `owner` | string/null | no | Follow-up owner. |
| `status` | string | yes | `open`, `accepted`, `closed`. |

## State Transitions

### Trace Status

```text
running -> success
running -> error
running -> partial
partial -> expired
success/error -> expired
```

### Payload Visibility

```text
redacted_trace -> masked_raw_reveal_requested -> masked_raw_revealed -> expired
redacted_trace -> blocked
```

MVP uses role-only authorization, so `masked_raw_reveal_requested` and
`masked_raw_revealed` may happen in one request after reason capture.

### Admin Grant

```text
active -> revoked
active -> expired
```

### Coverage Gap

```text
open -> accepted
open -> closed
accepted -> closed
```

## Retention Rules

| Record | Production Retention | Notes |
|---|---:|---|
| DashboardMetricSnapshot | 180 days | Queryable for PM reports. |
| ObservabilityTrace | 60 days | Redacted trace metadata and summaries. |
| ObservabilitySpan | 60 days | Same as trace. |
| ObservabilityPayload.masked_raw_json | 14 days | Must be purged or made inaccessible after expiry. |
| AdminAuditEvent | 180 days minimum | Must outlive masked raw payload retention for auditability. |
| DashboardSnapshot | 180 days | Aggregate/redacted only. |

## Indexing Guidance

- `ObservabilityTrace`: `(started_at DESC)`, `(user_id, started_at DESC)`,
  `(business_run_id)`, `(feature_area, started_at DESC)`, `(status, started_at DESC)`.
- `ObservabilitySpan`: `(trace_id, started_at)`, `(span_kind, name)`,
  `(agent_name, node_name)`.
- `LLMCallRecord`: `(trace_id)`, `(provider_request_id)`, `(model_requested)`,
  `(status, created_at DESC)`.
- `DashboardMetricSnapshot`: `(metric_id, period_start, period_end)`,
  `(freshness_at DESC)`, `(quality_state)`.
- `AdminAuditEvent`: `(actor_id, created_at DESC)`, `(target_type, target_id)`,
  `(action, created_at DESC)`.

# Trace Explorer API Contract

Base path: `/api/v1/admin-console/observability`

## GET `/traces`

Search traces across user, business, agent, node, LLM, eval, and badcase
dimensions.

Required capability: `TRACE_VIEW`.

Query:

| Parameter | Description |
|---|---|
| `user_id` | Exact user id, when permitted. |
| `anonymized_user_label` | Privacy-safe user label. |
| `business_run_id` | Resume/interview/error/eval business run id. |
| `trace_id` | Exact trace id. |
| `session_id` | Business or auth session id. |
| `feature_area` | Product area. |
| `agent_name` | Agent name. |
| `node_name` | Node name. |
| `model` | LLM model. |
| `prompt_version` | Prompt version/fingerprint. |
| `status` | `running`, `success`, `error`, `partial`, `expired`. |
| `error_type` | Error category. |
| `min_tokens`, `max_tokens` | Token range. |
| `min_cost`, `max_cost` | Estimated cost range. |
| `min_latency_ms`, `max_latency_ms` | Latency range. |
| `environment` | Environment. |
| `eval_status` | Eval pass/fail/incomplete. |
| `badcase_status` | Badcase status. |
| `date_from`, `date_to` | Time range. |
| `limit`, `cursor` | Pagination. |

Response 200:

```json
{
  "items": [
    {
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "started_at": "2026-06-29T12:00:00Z",
      "duration_ms": 2240,
      "status": "error",
      "feature_area": "interview",
      "business_run_id": "interview_123",
      "agent_name": "interview_supervisor",
      "llm_call_count": 4,
      "total_tokens": 3821,
      "estimated_cost": 0.0123,
      "eval_status": "failed",
      "badcase_status": "OPEN",
      "source_revision": "abc1234",
      "privacy_class": "sensitive_user_content"
    }
  ],
  "next_cursor": null,
  "freshness_at": "2026-06-29T12:01:00Z"
}
```

## GET `/traces/{trace_id}`

Returns trace hierarchy and safe details.

Response 200:

```json
{
  "trace": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "business_run_id": "interview_123",
    "feature_area": "interview",
    "status": "error",
    "started_at": "2026-06-29T12:00:00Z",
    "duration_ms": 2240
  },
  "spans": [
    {
      "span_id": "span_root",
      "parent_span_id": null,
      "span_kind": "agent_run",
      "name": "interview_supervisor",
      "status": "error",
      "duration_ms": 2240
    },
    {
      "span_id": "span_node_score",
      "parent_span_id": "span_root",
      "span_kind": "node",
      "name": "score",
      "node_name": "score",
      "status": "error",
      "duration_ms": 740,
      "input_payload_id": "payload_in",
      "output_payload_id": "payload_out",
      "state_diff_payload_id": "payload_diff"
    }
  ],
  "links": {
    "eval_case_ids": ["case_1"],
    "badcase_ids": ["badcase_1"]
  },
  "visibility_mode": "redacted_trace"
}
```

## GET `/agent-runs/{agent_run_id}`

Returns one agent run as graph/workflow execution.

Response 200 includes agent identity, graph identity, version context, node
timeline, final output summary, and linked LLM/tool/eval operations.

## GET `/nodes/{span_id}`

Returns node-level detail.

Response 200:

```json
{
  "span_id": "span_node_score",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "node_name": "score",
  "status": "error",
  "duration_ms": 740,
  "input": {
    "payload_id": "payload_in",
    "visibility_mode": "redacted_trace",
    "shape": {"answers": "array[5]", "rubric": "object"},
    "redacted_summary": "5 answers and scoring rubric present"
  },
  "output": {
    "payload_id": "payload_out",
    "visibility_mode": "redacted_trace",
    "shape": {"score": "number", "feedback": "string"},
    "redacted_summary": "Output failed schema validation"
  },
  "state_diff": {
    "payload_id": "payload_diff",
    "shape": {"score": "changed", "error": "added"}
  },
  "llm_calls": ["llm_1"],
  "tool_operations": []
}
```

## GET `/llm-calls/{llm_call_id}`

Returns one LLM call detail.

Response 200:

```json
{
  "llm_call_id": "llm_1",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "provider": "openai-compatible",
  "endpoint": "/v1/chat/completions",
  "http_method": "POST",
  "model_requested": "deepseek-v4-pro",
  "model_returned": "deepseek-v4-pro",
  "parameters": {
    "temperature": 0.2,
    "stream": true,
    "response_format": "json_schema"
  },
  "usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 320,
    "cache_tokens": 0,
    "reasoning_tokens": 0,
    "estimated_cost": 0.0042
  },
  "timing": {
    "latency_ms": 740,
    "time_to_first_token_ms": 210,
    "stream_chunk_count": 18
  },
  "status": "error",
  "finish_reason": null,
  "provider_request_id": "req_provider_123",
  "request_payload_id": "payload_req",
  "response_payload_id": "payload_resp"
}
```

## POST `/payloads/{payload_id}/reveal`

Reveals masked raw payload if permitted.

Required capability: `MASKED_RAW_VIEW`. Requires a non-empty reason.

Request:

```json
{
  "reason": "Investigating failed interview score",
  "visibility_mode": "masked_raw"
}
```

Response 200:

```json
{
  "payload_id": "payload_req",
  "visibility_mode": "masked_raw",
  "shape": {"messages": "array[3]", "model": "string"},
  "masked_raw": {
    "model": "deepseek-v4-pro",
    "messages": [
      {"role": "system", "content": "[MASKED_SYSTEM_PROMPT]"},
      {"role": "user", "content": "[MASKED_USER_TEXT]"}
    ]
  },
  "audit_id": "audit_019ef..."
}
```

Errors:

- 403 if actor lacks `MASKED_RAW_VIEW`.
- 422 if `reason` is missing.
- 410 if masked raw payload has expired.

## GET `/llm-calls/{llm_call_id}/curl`

Returns a safe reconstructed cURL command.

Required capability: `TRACE_VIEW`; `MASKED_RAW_VIEW` if including masked body.
Requires `reason` query parameter.

Response 200:

```json
{
  "llm_call_id": "llm_1",
  "visibility_mode": "redacted_trace",
  "curl": "curl https://api.example.com/v1/chat/completions -H 'Authorization: Bearer $PROVIDER_API_KEY' -H 'Content-Type: application/json' -d '{\"model\":\"deepseek-v4-pro\",\"messages\":\"[REDACTED]\"}'",
  "redacted_headers": ["Authorization", "Cookie"],
  "audit_id": "audit_019ef..."
}
```

Invariant:

- The returned command must never contain real API keys, bearer tokens, cookies,
  refresh tokens, private keys, or internal service credentials.

## GET `/coverage`

Returns Strong Debug MVP coverage across centralized Agent/LLM flows.

Response 200:

```json
{
  "generated_at": "2026-06-29T12:00:00Z",
  "covered_flows": [
    {
      "feature_area": "interview",
      "flow_name": "interview_supervisor",
      "coverage": "covered",
      "entrypoint": "centralized_agent_runner"
    }
  ],
  "gaps": [
    {
      "feature_area": "legacy",
      "flow_name": "direct_provider_call_example",
      "reason": "direct_provider_call",
      "severity": "medium",
      "status": "open"
    }
  ]
}
```

# Contract: Trace And Export Policy

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

This contract defines what observability records must carry and how external
destinations are authorized.

## Trace Context

Canonical propagation:

- Use W3C trace context for OTel propagation where possible.
- Preserve existing `X-Trace-Id` behavior as ingress/display compatibility.
- Every covered AI workflow must have a run id in addition to OTel trace id.

Required record fields:

| Field | Required | Notes |
|---|---|---|
| `run_id` | Yes for covered workflows | UUID string for eval/AI task correlation. |
| `trace_id` | Yes when OTel active | 32 lowercase hex; display as `"unavailable"` when absent. |
| `span_id` | When span exists | 16 lowercase hex. |
| `graph` | For agent workflows | Stable graph name. |
| `node` | For graph nodes/LLM calls | Stable node name. |
| `model` | For LLM calls | Provider model id. |
| `prompt_fingerprint` | For prompt-sensitive calls | Stable fingerprint, not raw prompt. |
| `rubric_version` | For judged/eval calls | Stable rubric version. |
| `experiment_id` | When assigned | Bounded string. |
| `variant` | When assigned | Baseline/candidate/named variant. |

## Span Attribute Policy

Allowed by default:

- Stable ids, graph/node names, model/provider names.
- Token counts, latency, retry count, cache status.
- Error class and sanitized error code.
- Prompt fingerprint and rubric version.
- Case id and run id.

Destination policy decides whether raw AI payloads are attached. Operational
secrets are never allowed.

## Destinations

### LOCAL_ARTIFACT

- Always allowed.
- Stores canonical reports and evidence.
- May contain full local debug payloads only where repository policy allows.

### LANGSMITH

- Allowed in local, CI, staging, and production when credentials and destination
  policy are configured.
- Production may use `FULL_CONTENT` representation and include complete
  unredacted AI payloads: resumes, job descriptions, interview free text, LLM
  inputs, and LLM outputs.
- Must not include operational secrets, credentials, access tokens, or
  infrastructure passwords.
- Must record destination, environment, owner, access scope, retention,
  policy version, and representation level.

### OTLP_GENERIC

- Used for vendor-neutral observability backends.
- Default representation is metadata-only or redacted summaries for sensitive
  AI payloads unless a future policy explicitly allows more.
- Must not receive raw AI payloads merely because LangSmith is allowed to.

## Export Decision Algorithm

1. Identify destination, environment, and requested representation level.
2. Load active destination policy.
3. Reject if required policy metadata is missing.
4. Reject if payload contains operational secrets.
5. For production LangSmith full-content export, allow raw AI payloads only when
   policy version, owner, access scope, and retention are present.
6. For non-approved destinations, transform to redacted/metadata-only or block.
7. Record `ExportPolicyDecision`.
8. Attempt export asynchronously or out-of-band where possible.
9. Report export status without changing local eval verdict or end-user AI
   workflow success.

## Sampling

- Eval and CI traces are sampled at 100% when OTel is enabled.
- Production success traces may be sampled according to policy.
- Production errors, failed eval-linked workflows, and promoted badcases should
  be retained at 100% where the backend supports tail sampling.
- Sampling decisions must be visible in export policy metadata.

## Failure Semantics

- End-user AI workflows fail open on export failure.
- Local eval verdicts are not changed by export failure.
- `require` sync modes may fail automation with exit `1` or `3`, but only by
  explicit command choice.
- Missing trace ids are reported as `"unavailable"` and counted as coverage
  failures for SC-004.

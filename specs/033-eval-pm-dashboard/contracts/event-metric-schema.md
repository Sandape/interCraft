# Contract: Event And Metric Schema

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

## Event Envelope

```json
{
  "eventName": "resume.diagnosis_completed",
  "occurredAt": "2026-06-26T00:00:00Z",
  "environment": "STAGING",
  "releaseStage": "RELEASE_CANDIDATE",
  "appVersion": "0.33.0",
  "actorHash": "hash-or-null",
  "userHash": "hash-or-null",
  "sessionHash": "hash-or-null",
  "threadHash": "hash-or-null",
  "featureArea": "RESUME",
  "graph": "resume_optimize",
  "node": "suggest_blocks",
  "runId": "run-or-null",
  "traceId": "trace-or-null",
  "caseId": "case-or-null",
  "promptFingerprint": "fingerprint-or-unknown",
  "rubricVersion": "version-or-unknown",
  "experimentId": "experiment-or-null",
  "privacyClass": "PUBLIC_METADATA",
  "redactionStatus": "NOT_REQUIRED",
  "metadata": {}
}
```

Validation:

- `eventName`, `occurredAt`, `environment`, `releaseStage`, `appVersion`,
  `featureArea`, `privacyClass`, `redactionStatus`, and `metadata` are required.
- Raw sensitive user content is not allowed in `metadata` for production export.
- Missing version fields use `unknown`; fields are not silently omitted.

## Event Catalog

| Event | Purpose |
|---|---|
| `product.visit` | Product entry signal. |
| `auth.registered` | Account created. |
| `auth.logged_in` | User authenticated. |
| `resume.created_or_uploaded` | Resume journey started. |
| `resume.diagnosis_requested` | Resume AI diagnosis started. |
| `resume.diagnosis_completed` | Resume AI diagnosis completed or failed. |
| `resume.report_viewed` | Diagnosis report viewed. |
| `resume.suggestion_shown` | Suggestion exposed to user. |
| `resume.suggestion_accepted` | Suggestion accepted by user. |
| `interview.started` | Mock interview started. |
| `interview.completed` | Mock interview completed. |
| `interview.report_viewed` | Interview report viewed. |
| `ai.call_completed` | AI call succeeded. |
| `ai.call_failed` | AI call failed. |
| `feedback.submitted` | User feedback captured. |
| `badcase.created` | Review item opened. |
| `badcase.classified` | Review item triaged. |
| `badcase.closed` | Review item resolved. |
| `eval.run_started` | Eval run began. |
| `eval.run_completed` | Eval run completed. |
| `eval.experiment_synced` | LangSmith sync succeeded or failed. |

## Metric Snapshot Envelope

```json
{
  "metricId": "ai.success_rate",
  "displayName": "AI Success Rate",
  "grain": "DAY",
  "periodStart": "2026-06-26T00:00:00Z",
  "periodEnd": "2026-06-27T00:00:00Z",
  "dimensions": {
    "environment": "STAGING",
    "appVersion": "0.33.0",
    "model": "deepseek",
    "graph": "interview",
    "node": "score"
  },
  "numerator": 98,
  "denominator": 100,
  "value": 0.98,
  "unit": "PERCENT",
  "sourceOfTruth": "ai_invocation_records",
  "freshnessAt": "2026-06-27T00:05:00Z",
  "qualityFlags": []
}
```

## Required Metric Definitions

| Metric ID | Unit | Numerator | Denominator | Source |
|---|---|---|---|---|
| `product.uv` | count | unique visitor/session/user hash count | n/a | product events |
| `product.registered_users` | count | registration events | n/a | auth events |
| `product.active_users` | count | active user hash count | n/a | product events |
| `funnel.step_conversion` | percent | users reaching step N | users reaching step N-1 | product events |
| `resume.diagnosis_success_rate` | percent | completed diagnoses | requested diagnoses | resume events |
| `resume.suggestion_acceptance_rate` | percent | accepted suggestions | shown suggestions | resume events |
| `resume.score_delta` | score | after score - before score | n/a | diagnosis outcomes |
| `interview.completion_rate` | percent | completed interviews | started interviews | interview outcomes |
| `interview.average_question_count` | count | total answered/generated questions | completed or started interviews | interview outcomes |
| `ai.call_count` | count | AI invocation records | n/a | AI invocation records |
| `ai.success_rate` | percent | successful AI calls | all AI calls | AI invocation records |
| `ai.estimated_cost` | currency | estimated cost sum | n/a | AI invocation records |
| `ai.latency_p95_ms` | milliseconds | p95 latency | n/a | AI invocation records |
| `badcase.open_count` | count | open/triaged/in-progress badcases | n/a | badcases |
| `badcase.closure_rate` | percent | closed badcases | closed + open + rejected badcases | badcases |
| `version.prompt_known_rate` | percent | records with known prompt fingerprint | eligible records | event/AI/eval records |

## Privacy And Export Rules

| Environment | Allowed External Payload |
|---|---|
| `LOCAL` | Developer-controlled; prefer synthetic/golden data. |
| `CI` | Synthetic or approved version-controlled golden data. |
| `STAGING` | Masked prompt/output only for synthetic, golden, or approved staging test data; otherwise metadata + redacted summaries. |
| `PRODUCTION` | Metadata + redacted summaries only, retained 30 days. |

Forbidden everywhere:

- Secrets, access tokens, refresh tokens, API keys, passwords.

Forbidden in production external export:

- Raw resumes.
- Raw interview answers.
- Raw job descriptions.
- Raw free-form chat or feedback text.

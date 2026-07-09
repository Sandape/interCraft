# Data Model: REQ-033 Automated Eval & PM Dashboard MVP

**Spec**: [./spec.md](./spec.md) | **Plan**: [./plan.md](./plan.md)

This file defines planning-level entities and validation rules. Exact table
names may be adjusted during tasks, but the fields and relationships are the
contract for implementation.

## Entity Relationship Overview

```text
GoldenCase ─┬─< EvalCaseResult >─ EvalRun ── LangSmithExperimentRef
            │                         │
            │                         ├── TraceRunRef
            │                         └── BadcaseEvidence
            │
ProductFunnelEvent ──> PMMetricSnapshot <── MetricDefinition
AIInvocationRecord ──┘        │
ResumeDiagnosisOutcome ───────┤
InterviewOutcome ─────────────┤
FeedbackSignal ───────────────┘

Badcase ──< BadcaseEvidence
Badcase ──< BadcaseReviewAction
Badcase ── optional promotion ──> GoldenCase

RedactionPolicy ──< RedactionAudit
RedactionAudit ── validates ──> exportable EvalRun / TraceRunRef / BadcaseEvidence
```

## Shared Value Objects

### VersionContext

| Field | Required | Rule |
|---|---:|---|
| `appVersion` | yes | Product version or explicit `unknown`. |
| `releaseStage` | yes | `DEVELOPMENT`, `RELEASE_CANDIDATE`, `PRODUCTION`, or `UNKNOWN`. |
| `environment` | yes | `LOCAL`, `CI`, `STAGING`, `PRODUCTION`. |
| `promptFingerprint` | conditional | Required for AI/eval records, otherwise `unknown`. |
| `rubricVersion` | conditional | Required for scored AI/eval records, otherwise `unknown`. |
| `model` | conditional | Required for AI/eval records, otherwise `unknown`. |
| `experimentId` | conditional | Required when an experiment group exists. |
| `graph` | conditional | Required for agent/eval events. |
| `node` | conditional | Required for node-level agent/eval events. |
| `schemaVersion` | yes | Event/report schema version. |

### PrivacyClassification

| Value | Meaning | Export Default |
|---|---|---|
| `PUBLIC_METADATA` | Non-sensitive operational metadata | Exportable |
| `INTERNAL_METADATA` | Hashes or normalized internal identifiers | Exportable if policy permits |
| `SENSITIVE_USER_CONTENT` | Raw resume, JD, interview answer, free-form text | Not exportable in production |
| `SECRET` | Token, password, API key, credential | Never exportable |
| `REDACTED_SUMMARY` | Approved derived summary after redaction | Exportable if audit passes |

### RedactionStatus

`NOT_REQUIRED`, `PENDING`, `PASSED`, `FAILED`, `NOT_EXPORTABLE`

## Core Entities

### GoldenCase

| Field | Rule |
|---|---|
| `caseId` | Stable unique id, version controlled. |
| `graph` / `node` | Required. |
| `schemaVersion` | Required. |
| `status` | `ACTIVE`, `STALE`, `SUPERSEDED`, `REJECTED`. |
| `source` | `MANUAL`, `PROMOTED_BADCASE`, `SYNTHETIC`, `STAGING_APPROVED`. |
| `inputPrivacyClass` | Required. Blocks upload if sensitive and not approved. |
| `expectedOutput` / `rubric` | At least one required. |
| `uploadPolicy` | `LANGSMITH_ALLOWED`, `LOCAL_ONLY`, `NEEDS_REVIEW`. |
| `reviewer` | Required for promoted or user-derived cases. |

### EvalRun

| Field | Rule |
|---|---|
| `runId` | Stable id shared across local report, CI artifact, LangSmith sync, and badcase evidence. |
| `sourceRevision` / `branch` | Required. |
| `environment` | Required. |
| `status` | `STARTED`, `PASSED`, `FAILED`, `INCOMPLETE`, `SYNC_FAILED`. |
| `startedAt` / `completedAt` | Required when known. |
| `aggregatePassRate` | Required on completion. |
| `knownRegressionRecall` | Required for PR/nightly reports. |
| `staleCaseCount` | Required on completion. |
| `budgetTokens` / `budgetCost` | Required for nightly real-model eval. |
| `versionContext` | Required. |

### EvalCaseResult

| Field | Rule |
|---|---|
| `runId` | FK-like reference to EvalRun. |
| `caseId` | FK-like reference to GoldenCase. |
| `verdict` | `PASS`, `FAIL`, `STALE`, `SKIPPED`, `ERROR`. |
| `failureReason` | Required when verdict is fail/error. |
| `metrics` | Structured metric map; no raw production content. |
| `traceId` | Optional, present when trace exists and policy permits. |
| `artifactRef` | Local artifact path or CI artifact id. |

### LangSmithExperimentRef

| Field | Rule |
|---|---|
| `runId` | Required join id. |
| `project` | `intercraft-{environment}` naming. |
| `dataset` | Includes graph/node/schema version. |
| `experimentName` | Includes run id, branch, source revision. |
| `externalId` / `url` | Optional until sync succeeds. |
| `syncStatus` | `DISABLED`, `PENDING`, `SYNCED`, `FAILED`. |
| `syncError` | Required when failed. |
| `syncedAt` | Required when synced. |

### TraceRunRef

| Field | Rule |
|---|---|
| `traceId` | Required when trace exists. |
| `runId` | Optional for non-eval traces. |
| `environment` | Required. |
| `samplingDecision` | `ALWAYS_ERROR`, `SAMPLED`, `FORCED`, `DROPPED`, `NOT_ENABLED`. |
| `privacyClass` | Required. |
| `redactionStatus` | Required before external export. |
| `retentionExpiresAt` | Required for production; exactly 30 days after creation/export. |

### ProductFunnelEvent

| Field | Rule |
|---|---|
| `eventName` | Must be from approved event catalog. |
| `occurredAt` | Required. |
| `actorHash` / `userHash` / `sessionHash` | Optional based on policy; raw ids not exported externally. |
| `featureArea` | `AUTH`, `RESUME`, `INTERVIEW`, `AI`, `FEEDBACK`, `BADCASE`, `EVAL`. |
| `versionContext` | Required. |
| `privacyClass` | Required. |
| `metadata` | Structured and policy-limited. |

### AIInvocationRecord

| Field | Rule |
|---|---|
| `invocationId` | Unique id. |
| `runId` / `traceId` | Optional join ids. |
| `graph` / `node` | Required. |
| `model` | Required or `unknown`. |
| `promptFingerprint` | Required or `unknown`. |
| `promptTokens` / `completionTokens` | Required when available. |
| `estimatedCost` | Labeled as estimate. |
| `latencyMs` | Required when available. |
| `retryCount` | Required. |
| `status` | `SUCCESS`, `FAILURE`, `TIMEOUT`, `CANCELLED`. |
| `errorCategory` | Required for failure. |

### PMMetricSnapshot

| Field | Rule |
|---|---|
| `metricId` | Stable id from MetricDefinition. |
| `periodStart` / `periodEnd` | Required. |
| `grain` | `DAY`, `WEEK`, `RELEASE`, `EVAL_RUN`. |
| `dimensions` | Structured approved dimensions only. |
| `numerator` / `denominator` | Required for rates. |
| `value` | Required. |
| `unit` | `COUNT`, `PERCENT`, `TOKENS`, `CURRENCY`, `MILLISECONDS`, `SCORE`, `DAYS`. |
| `sourceOfTruth` | Required. |
| `freshnessAt` | Required. |
| `qualityFlags` | Missing version fields, sampled data, delayed ingestion, partial data. |

### Badcase

| Field | Rule |
|---|---|
| `badcaseId` | Unique id. |
| `type` | Resume quality, interview quality, AI reliability, cost/latency, UX/funnel, data quality, privacy/redaction, eval regression. |
| `severity` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. |
| `status` | `OPEN`, `TRIAGED`, `IN_PROGRESS`, `AWAITING_VALIDATION`, `CLOSED`, `REJECTED`. |
| `source` | Eval failure, staging trace, user feedback, PM review, manual entry. |
| `reviewer` | Required for classification and closure. |
| `privacyClass` | Required. |
| `redactionStatus` | Required when promotion/export is involved. |
| `runId` / `traceId` | Optional but required when source provides one. |
| `closureReason` | Required for closed/rejected. |
| `closedAt` | Required for closed/rejected. |

### BadcaseReviewAction

| Field | Rule |
|---|---|
| `actionType` | `CREATE`, `CLASSIFY`, `PROMOTE_CANDIDATE`, `APPROVE_PROMOTION`, `CLOSE`, `REJECT`, `OVERRIDE`, `BASELINE_REFRESH`. |
| `actorRole` | PM business owner, technical owner, badcase reviewer, automation. |
| `reason` | Required for close, reject, override, baseline refresh, promotion. |
| `evidenceRef` | Required for close, override, baseline refresh, promotion. |
| `createdAt` | Required. |

### RedactionPolicy

| Field | Rule |
|---|---|
| `policyVersion` | Required. |
| `environment` | Required. |
| `allowedClasses` | Required. |
| `forbiddenClasses` | Required. |
| `summaryRules` | Required for redacted summaries. |
| `retentionDays` | Production is 30 days. |
| `requiresHumanReview` | True for production enablement and promotion flows. |

### RedactionAudit

| Field | Rule |
|---|---|
| `auditId` | Unique id. |
| `policyVersion` | Required. |
| `environment` | Required. |
| `sampleCount` | Required. |
| `forbiddenContentFailures` | Required count. |
| `result` | `PASSED`, `FAILED`, `INCOMPLETE`. |
| `reviewer` | Required before production enablement. |
| `evidenceRef` | Required. |

## State Transitions

### Badcase

```text
OPEN -> TRIAGED -> IN_PROGRESS -> AWAITING_VALIDATION -> CLOSED
OPEN -> REJECTED
TRIAGED -> REJECTED
AWAITING_VALIDATION -> IN_PROGRESS
```

Rules:

- `CLOSED` requires closure reason, evidence/rationale, reviewer, timestamp.
- `REJECTED` requires rejection reason.
- Promotion to GoldenCase is an action, not a terminal badcase state.
- First-month promotion uses CLI/documented review flow.

### EvalRun

```text
STARTED -> PASSED
STARTED -> FAILED
STARTED -> INCOMPLETE
PASSED/FAILED -> SYNCED_TO_LANGSMITH
PASSED/FAILED -> LANGSMITH_SYNC_FAILED
```

Rules:

- LangSmith sync failure does not change local eval verdict.
- Baseline refresh from a run requires PM business owner + technical owner dual
  approval.

## Validation Rules

- Any raw resume, interview answer, JD text, free-form text, or secret in a
  production export payload fails redaction validation.
- Missing version fields must be represented as explicit `unknown` and counted
  in quality flags.
- List/query contracts must support date range and pagination where records are
  returned.
- All externally visible errors use a structured error shape with code, message,
  and optional details.
- Production trace records must become inaccessible after 30 days.

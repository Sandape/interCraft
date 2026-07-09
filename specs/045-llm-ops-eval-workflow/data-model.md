# Data Model: REQ-045 LLM Ops Eval Workflow

## Shared Types

- **RunId**: UUID string identifying one eval or AI task execution.
- **TraceId**: 32-character lowercase hex OTel trace id, or `"unavailable"` in
  display/report contexts where no trace exists.
- **SpanId**: 16-character lowercase hex OTel span id when available.
- **CaseId**: Stable dataset case identifier.
- **SourceRevision**: Git SHA or CI source revision string.
- **Environment**: `LOCAL`, `CI`, `STAGING`, `PRODUCTION`.
- **RepresentationLevel**: `FULL_CONTENT`, `REDACTED`, `METADATA_ONLY`,
  `BLOCKED`.
- **ExportDestination**: `LOCAL_ARTIFACT`, `LANGSMITH`, `OTLP_GENERIC`.
- **ExportStatus**: `DISABLED`, `PENDING`, `SYNCED`, `FAILED`, `PARTIAL`.
- **EvalCaseLifecycle**: `GOLDEN`, `CANDIDATE`, `REPORT_ONLY`, `DEPRECATED`,
  `REJECTED`.
- **JudgeCalibrationStatus**: `DRAFT`, `REPORT_ONLY`, `CALIBRATED`,
  `WAIVED`, `BLOCKING_ENABLED`, `BLOCKING_DISABLED`.
- **ProposalStatus**: `DRAFT`, `READY_FOR_COMPARISON`, `COMPARED`,
  `APPROVED`, `REJECTED`, `APPLIED`.

## Entities

### EvalRun

Represents one evaluation execution.

Fields:

- `runId`: RunId, required.
- `suite`: string, required.
- `environment`: Environment, required.
- `status`: `CREATED`, `RUNNING`, `PASSED`, `FAILED`, `INCOMPLETE`, `ERROR`.
- `sourceRevision`: SourceRevision, required for CI/staging/production.
- `branch`: string, optional.
- `datasetVersion`: string, required.
- `promptFingerprint`: string, required when prompt content affects cases.
- `rubricVersion`: string, required when rubric content affects cases.
- `modelVersion`: string, required for real-model runs.
- `startedAt`, `finishedAt`: timestamps.
- `aggregatePassRate`: float 0..1.
- `knownRegressionRecall`: float 0..1.
- `tokenUsage`, `costUsd`, `latencyMs`: numeric summaries.
- `localArtifacts`: JSON/Markdown/report paths.
- `langsmithExportStatus`: ExportStatus.
- `exportPolicyDecisionId`: optional reference.

Relationships:

- Has many `EvalCaseResult`.
- May have one `LangSmithExperimentRef`.
- May have many `JudgeVerdict`.
- May have many `ExperimentAssignment` contexts.

Validation:

- Local artifacts are required before `PASSED` or `FAILED`.
- LangSmith export status cannot change local pass/fail status.
- `sourceRevision` is required for CI and production evidence.

### EvalCaseResult

Represents one case inside an eval run.

Fields:

- `caseId`: CaseId, required.
- `runId`: RunId, required.
- `lifecycle`: EvalCaseLifecycle, required.
- `graph`: string, required.
- `node`: string, required.
- `passed`: boolean.
- `failureReasons`: string array.
- `deterministicMetrics`: object.
- `expectedFidelityPass`: boolean, optional.
- `artifactRef`: string, required or `"unavailable"`.
- `traceRunRefId`: optional reference.
- `langsmithRunUrl`: string or `"unavailable"`.
- `judgeVerdictIds`: list.

Relationships:

- Belongs to `EvalRun`.
- May link to `TraceRunRef`.
- May link to `BadcasePromotionCandidate`.
- May have many `JudgeVerdict`.

Validation:

- Golden cases may block merges; candidate/report-only cases cannot block.
- Missing links render as `"unavailable"` rather than omitted fields.

### TraceRunRef

Correlation envelope for local artifacts, OTel traces, and LangSmith runs.

Fields:

- `traceRunRefId`: stable id.
- `runId`: RunId.
- `caseId`: CaseId, optional.
- `traceId`: TraceId or null internally.
- `spanId`: SpanId, optional.
- `artifactRef`: string, optional.
- `langsmithUrl`: string, optional.
- `entrypoint`: API route, CLI command, job name, or websocket channel.
- `createdAt`: timestamp.

Validation:

- `traceId` must be 32 lowercase hex when present.
- Display helpers must map null/empty/unknown to `"unavailable"`.

### LangSmithExperimentRef

External LangSmith reference for synced workbench data.

Fields:

- `langsmithRefId`: stable id.
- `runId`: RunId.
- `project`: string.
- `datasetName`: string.
- `datasetVersion`: string.
- `experimentName`: string.
- `experimentUrl`: URL.
- `syncStatus`: ExportStatus.
- `syncedAt`: timestamp.
- `errorCode`, `errorMessage`: optional, sanitized.

Validation:

- Failed sync must preserve local eval verdict.
- URL is required only when `syncStatus == SYNCED`.

### JudgeRubric

Versioned evaluator definition for subjective quality.

Fields:

- `rubricId`: stable id.
- `name`: string.
- `version`: string.
- `dimensions`: list of scoring dimensions.
- `scale`: scoring scale definition.
- `judgeModel`: string.
- `calibrationStatus`: JudgeCalibrationStatus.
- `humanLabelCount`: integer.
- `agreementRate`: float 0..1.
- `owner`: string.
- `createdAt`, `updatedAt`: timestamps.

Validation:

- Cannot become `BLOCKING_ENABLED` unless human label count >= 30 and agreement
  rate >= 0.80, or an owner waiver is recorded.

### JudgeVerdict

One LLM-as-Judge result.

Fields:

- `verdictId`: stable id.
- `runId`: RunId.
- `caseId`: CaseId.
- `rubricId`: reference.
- `rubricVersion`: string.
- `judgeModel`: string.
- `judgeVersion`: string.
- `score`: numeric.
- `confidence`: numeric 0..1.
- `rationaleSummary`: short string.
- `disagreementMarkers`: string array.
- `isBlocking`: boolean.
- `createdAt`: timestamp.

Validation:

- `rationaleSummary` must not include operational secrets.
- `isBlocking` must be false unless the rubric is blocking-enabled.

### ExperimentAssignment

Variant context for eval and production comparison.

Fields:

- `experimentId`: string.
- `variant`: `BASELINE`, `CANDIDATE`, or named variant.
- `runId`: RunId.
- `datasetVersion`: string.
- `promptFingerprint`: string.
- `rubricVersion`: string.
- `modelVersion`: string.
- `sourceRevision`: SourceRevision.
- `assignedAt`: timestamp.

Validation:

- A comparison requires one baseline and at least one candidate on the same
  dataset version unless explicitly marked exploratory.

### AIInvocationRecord

Persistent representation of an LLM call.

Fields:

- `invocationId`: stable id.
- `runId`: RunId, optional but required for covered workflows.
- `traceId`: TraceId, optional but required for covered workflows when OTel is
  active.
- `spanId`: SpanId, optional.
- `provider`: string.
- `model`: string.
- `graph`: string.
- `node`: string.
- `promptFingerprint`: string.
- `inputTokens`, `outputTokens`, `totalTokens`: integers.
- `latencyMs`: integer.
- `cacheStatus`: enum or string.
- `errorClass`: string, optional.
- `experimentId`, `variant`: optional.
- `createdAt`: timestamp.

Validation:

- Covered workflow success target: at least 95% have trace/run correlation.
- Raw prompt/output storage follows the active destination/local storage policy.

### ExportPolicyDecision

Authorization and representation decision before external export.

Fields:

- `decisionId`: stable id.
- `destination`: ExportDestination.
- `environment`: Environment.
- `representationLevel`: RepresentationLevel.
- `policyVersion`: string.
- `owner`: string.
- `accessScope`: string.
- `retentionDays`: integer.
- `allowedContentClasses`: string array.
- `blockedReason`: string, optional.
- `sampleRate`: number 0..1.
- `createdAt`: timestamp.

Validation:

- Production LangSmith may use `FULL_CONTENT` only with explicit owner, access
  scope, retention, and policy version.
- `OTLP_GENERIC` must not receive full raw AI payloads unless a future policy
  explicitly allows it.
- Operational secrets are never allowed.

### BadcasePromotionCandidate

Candidate eval case derived from production/staging evidence.

Fields:

- `candidateId`: stable id.
- `sourceBadcaseId`: string.
- `sourceTraceRunRefId`: reference.
- `caseId`: CaseId, optional until accepted.
- `lifecycle`: EvalCaseLifecycle.
- `owner`: string.
- `reviewStatus`: `PENDING`, `APPROVED`, `REJECTED`.
- `exportPolicyDecisionId`: reference.
- `approvalReason`: string.
- `createdAt`, `approvedAt`: timestamps.

Validation:

- Cannot become golden without human approval metadata.
- Candidate/report-only cases cannot block merges.

### PromptImprovementProposal

Human-reviewed prompt or rubric change proposal.

Fields:

- `proposalId`: stable id.
- `status`: ProposalStatus.
- `sourceRunIds`: RunId list.
- `sourceCaseIds`: CaseId list.
- `targetGraph`: string.
- `targetNode`: string.
- `proposalType`: `PROMPT`, `RUBRIC`, `DATASET`, `EVALUATOR`.
- `candidateFingerprint`: string.
- `expectedImpact`: string.
- `comparisonRunId`: RunId, optional.
- `approvalOwner`: string, optional.
- `createdAt`, `updatedAt`: timestamps.

Validation:

- Cannot become `APPROVED` without baseline/candidate comparison evidence.
- Cannot become `APPLIED` without explicit human approval.

## State Transitions

### EvalRun

```text
CREATED -> RUNNING -> PASSED
                  -> FAILED
                  -> INCOMPLETE
                  -> ERROR
```

LangSmith export status is independent:

```text
DISABLED
PENDING -> SYNCED
        -> PARTIAL
        -> FAILED
```

### Eval Case Lifecycle

```text
CANDIDATE -> REPORT_ONLY -> GOLDEN
          -> REJECTED
GOLDEN -> DEPRECATED
```

### Judge Rubric Lifecycle

```text
DRAFT -> REPORT_ONLY -> CALIBRATED -> BLOCKING_ENABLED
                         |             |
                         v             v
                       WAIVED      BLOCKING_DISABLED
```

### Prompt Proposal Lifecycle

```text
DRAFT -> READY_FOR_COMPARISON -> COMPARED -> APPROVED -> APPLIED
                                      |          |
                                      v          v
                                   REJECTED   REJECTED
```

## Foundation Implementation Notes

- Runtime records use `llm_ops_*` table names so REQ-045 does not collide with
  historical REQ-033 tables such as `eval_runs`, `trace_run_refs`, and
  `langsmith_experiment_refs`.
- Shared Pydantic schemas live in `backend/app/eval/schemas.py`; they remain
  persistence-neutral so local JSON/Markdown artifacts and database rows can
  share validation without making the database the local eval verdict source.
- Export governance value objects live in
  `backend/app/modules/telemetry_contracts/export_policy.py`. Production
  LangSmith full-content export requires owner, access scope, retention, policy
  version, and explicit content classes. Operational secrets are blocked before
  every external export decision.
- Foundation metrics in `backend/app/core/metrics.py` use bounded labels only:
  suite, environment, status, destination, representation level, decision,
  rubric, surface, and sync mode. Run IDs, trace IDs, case IDs, user IDs, and
  prompt/output content stay out of metric labels.
- The first migration is `backend/migrations/versions/0045_llm_ops_eval_workflow.py`
  and attaches to the current project migration head `0027_021_eq_arch`.

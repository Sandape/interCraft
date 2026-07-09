# Contract: AI Ops Evidence API

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

These backend contracts expose REQ-045 evidence to PM/admin surfaces. They are
additive to existing dashboard/admin modules and do not require a redesign.

## Shared Rules

- JSON fields use camelCase.
- List endpoints are paginated.
- Filters use query parameters.
- Error responses use a stable shape:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request",
    "details": {}
  }
}
```

Status codes:

- `400`: malformed input.
- `401`: not authenticated.
- `403`: not authorized.
- `404`: resource not found.
- `409`: lifecycle conflict.
- `422`: semantically invalid request.
- `500`: server error without internal details.

## List Eval Runs

```text
GET /api/admin/ai-ops/eval-runs?environment=CI&status=FAILED&page=1&pageSize=20
```

Response:

```json
{
  "data": [
    {
      "runId": "7b95b3c3-3f31-4097-8982-4dc3f8f455c0",
      "suite": "golden",
      "environment": "CI",
      "status": "FAILED",
      "sourceRevision": "abc123",
      "datasetVersion": "golden-v2",
      "aggregatePassRate": 0.92,
      "knownRegressionRecall": 1.0,
      "langsmithExportStatus": "SYNCED",
      "startedAt": "2026-07-05T01:00:00Z",
      "finishedAt": "2026-07-05T01:03:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalItems": 1,
    "totalPages": 1
  }
}
```

## Get Eval Run Detail

```text
GET /api/admin/ai-ops/eval-runs/{runId}
```

Response includes top-level eval summary, case results, trace references,
LangSmith references, export policy decision, judge verdict summaries, and
artifact links.

## Compare Experiments

```text
POST /api/admin/ai-ops/experiments/compare
```

Request:

```json
{
  "baselineRunId": "run-baseline",
  "candidateRunId": "run-candidate"
}
```

Response:

```json
{
  "comparisonId": "cmp_01J...",
  "baselineRunId": "run-baseline",
  "candidateRunId": "run-candidate",
  "qualityDelta": 0.03,
  "knownRegressionDelta": 0.0,
  "costDeltaUsd": 0.42,
  "latencyDeltaMs": -1200,
  "judgeScoreDelta": 0.04,
  "confidenceWarnings": [],
  "recommendation": "PROMOTE_CANDIDATE_WITH_REVIEW"
}
```

## Get Export Policy Decisions

```text
GET /api/admin/ai-ops/export-policies?destination=LANGSMITH&environment=PRODUCTION&page=1&pageSize=20
```

Response entries include decision id, destination, environment,
representation level, owner, access scope, retention, policy version, result,
and created timestamp.

## Promote Badcase

```text
POST /api/admin/ai-ops/badcases/{badcaseId}/promotions
```

Request:

```json
{
  "targetSuite": "golden",
  "reviewer": "alice@example.com",
  "exportPolicyDecisionId": "epd_01J...",
  "reason": "Protect production regression"
}
```

Response:

```json
{
  "candidateId": "bpc_01J...",
  "sourceBadcaseId": "badcase-123",
  "lifecycle": "CANDIDATE",
  "reviewStatus": "APPROVED",
  "caseId": "candidate-badcase-123",
  "canBlockMerges": false
}
```

## Prompt Proposals

```text
GET /api/admin/ai-ops/prompt-proposals?page=1&pageSize=20
POST /api/admin/ai-ops/prompt-proposals
POST /api/admin/ai-ops/prompt-proposals/{proposalId}/approve
POST /api/admin/ai-ops/prompt-proposals/{proposalId}/reject
```

Rules:

- Approval requires comparison evidence.
- Rejection requires a reason.
- Applying a prompt is outside this contract unless a later requirement adds a
  deployment workflow.

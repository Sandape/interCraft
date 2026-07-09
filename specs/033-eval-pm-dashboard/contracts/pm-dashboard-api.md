# Contract: PM Dashboard V1 API

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

This contract defines PM-facing internal API shapes. Exact route registration is
implementation work; the request/response semantics below are the contract.

## Shared Request Filters

All dashboard endpoints accept these query parameters unless noted otherwise.

| Param | Required | Notes |
|---|---:|---|
| `dateFrom` | yes | Inclusive ISO date/time. |
| `dateTo` | yes | Exclusive ISO date/time. |
| `environment` | no | `local`, `ci`, `staging`, `production`; defaults to PM-authorized environments. |
| `releaseStage` | no | Development/release-candidate/production. |
| `appVersion` | no | Exact version or `unknown`. |
| `promptFingerprint` | no | Exact fingerprint or `unknown`. |
| `rubricVersion` | no | Exact version or `unknown`. |
| `model` | no | Model id or `unknown`. |
| `experimentId` | no | Experiment id/group. |
| `graph` | no | Agent graph. |
| `node` | no | Agent node. |

## Shared Response Envelope

```json
{
  "filters": {},
  "freshnessAt": "2026-06-26T00:00:00Z",
  "qualityFlags": [],
  "data": {}
}
```

## Error Shape

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid dashboard filter",
    "details": {}
  }
}
```

Status semantics:

- `400`: invalid date range or query syntax.
- `401`: not authenticated.
- `403`: authenticated but not authorized for PM dashboard.
- `422`: semantically invalid filter combination.
- `500`: server error without sensitive details.

## Endpoints

### GET `/api/v1/pm-dashboard/overview`

Returns product overview metrics.

```json
{
  "data": {
    "uv": 120,
    "registeredUsers": 24,
    "activeUsers": 78,
    "completedAiTasks": 96,
    "aiSuccessRate": 0.97,
    "totalTokens": 1234567,
    "estimatedCost": {"amount": 42.5, "currency": "USD", "isEstimate": true},
    "openBadcases": 7
  }
}
```

### GET `/api/v1/pm-dashboard/funnel`

Returns the required core funnel.

```json
{
  "data": {
    "steps": [
      {
        "eventName": "product.visit",
        "count": 1000,
        "conversionFromPrevious": 1.0,
        "conversionFromEntry": 1.0,
        "isLargestDropoff": false
      }
    ]
  }
}
```

### GET `/api/v1/pm-dashboard/resume-diagnosis`

Returns resume diagnosis and suggestion adoption metrics.

```json
{
  "data": {
    "diagnosisCount": 80,
    "successRate": 0.95,
    "failureRate": 0.05,
    "reportViews": 60,
    "suggestionsShown": 240,
    "suggestionsAccepted": 96,
    "acceptanceRate": 0.4,
    "scoreDelta": {"average": 8.2, "unit": "score"}
  }
}
```

### GET `/api/v1/pm-dashboard/mock-interview`

Returns mock interview usage and completion metrics.

```json
{
  "data": {
    "starts": 50,
    "completions": 34,
    "completionRate": 0.68,
    "averageQuestionCount": 4.6,
    "reportViews": 30,
    "retries": 8,
    "failureRate": 0.06
  }
}
```

### GET `/api/v1/pm-dashboard/ai-operations`

Returns AI call volume, cost, latency, reliability, and version segments.

```json
{
  "data": {
    "callCount": 320,
    "successRate": 0.98,
    "failureRate": 0.02,
    "retryCount": 18,
    "latencyMs": {"p50": 900, "p95": 4200},
    "tokens": {"prompt": 900000, "completion": 220000, "total": 1120000},
    "estimatedCost": {"amount": 38.2, "currency": "USD", "isEstimate": true},
    "segments": [
      {
        "model": "unknown",
        "promptFingerprint": "unknown",
        "graph": "interview",
        "node": "score",
        "callCount": 40,
        "successRate": 1.0
      }
    ]
  }
}
```

### GET `/api/v1/pm-dashboard/feedback-badcases`

Returns feedback and badcase health.

```json
{
  "data": {
    "thumbsUp": 20,
    "thumbsDown": 5,
    "helpfulnessAverage": 4.1,
    "textFeedbackCount": 12,
    "badcases": {
      "open": 7,
      "closed": 9,
      "closureRate": 0.56,
      "byType": [{"type": "AI_RELIABILITY", "count": 3}],
      "bySeverity": [{"severity": "HIGH", "count": 1}]
    }
  }
}
```

### GET `/api/v1/pm-dashboard/version-experiments`

Returns version and experiment attribution coverage.

```json
{
  "data": {
    "versionCoverage": {
      "appVersionKnownRate": 0.99,
      "promptFingerprintKnownRate": 0.96,
      "rubricVersionKnownRate": 0.94
    },
    "experiments": [
      {
        "experimentId": "exp-20260626",
        "group": "candidate",
        "runId": "run-123",
        "traceCoverage": 0.8
      }
    ]
  }
}
```

## List Contract For Badcases

### GET `/api/v1/badcases`

Query params: shared filters plus `status`, `type`, `severity`, `source`,
`reviewer`, `page`, `pageSize`, `sortBy`, `sortOrder`.

Response:

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalItems": 0,
    "totalPages": 0
  }
}
```

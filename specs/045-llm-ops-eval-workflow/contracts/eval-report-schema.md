# Contract: Eval Report Schema

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

The local eval report is the canonical CI artifact and the input to optional
LangSmith sync. JSON fields use camelCase. Missing optional references render
as `"unavailable"` in reports.

## Top-Level Shape

```json
{
  "schemaVersion": "045.eval-report.v1",
  "runId": "7b95b3c3-3f31-4097-8982-4dc3f8f455c0",
  "suite": "golden",
  "environment": "CI",
  "status": "PASSED",
  "sourceRevision": "abc123",
  "branch": "codex/045-llm-ops-eval-workflow",
  "datasetVersion": "golden-v2",
  "promptFingerprint": "pf_...",
  "rubricVersion": "rv_...",
  "modelVersion": "deepseek-v4-2026-07",
  "startedAt": "2026-07-05T01:00:00Z",
  "finishedAt": "2026-07-05T01:03:00Z",
  "aggregatePassRate": 1.0,
  "knownRegressionRecall": 1.0,
  "tokenUsage": {
    "inputTokens": 1000,
    "outputTokens": 500,
    "totalTokens": 1500
  },
  "costUsd": 0.12,
  "latencyMs": 180000,
  "langsmithExportStatus": "SYNCED",
  "exportPolicyDecisionId": "epd_01J...",
  "langsmithUrl": "https://smith.langchain.com/...",
  "artifacts": {
    "json": "docs/evidence/<run_id>/eval-report.json",
    "markdown": "docs/evidence/<run_id>/eval-report.md"
  },
  "caseResults": []
}
```

## Case Result

```json
{
  "caseId": "interview-score-regression-001",
  "runId": "7b95b3c3-3f31-4097-8982-4dc3f8f455c0",
  "lifecycle": "GOLDEN",
  "graph": "interview",
  "node": "interview.score_llm",
  "passed": true,
  "failureReasons": [],
  "deterministicMetrics": {
    "chineseFidelityPassed": true,
    "expectedKeywordRecall": 1.0
  },
  "expectedFidelityPass": true,
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "spanId": "00f067aa0ba902b7",
  "artifactRef": "docs/evidence/<run_id>/cases/interview-score-regression-001.json",
  "langsmithUrl": "https://smith.langchain.com/...",
  "judgeVerdicts": []
}
```

Rules:

- `runId` is required on every case result.
- `traceId`, `artifactRef`, and `langsmithUrl` must be present as values or
  `"unavailable"`.
- `lifecycle` controls gate behavior. Only `GOLDEN` cases may block merges.

## Judge Verdict

```json
{
  "verdictId": "jv_01J...",
  "caseId": "interview-score-regression-001",
  "rubricId": "coaching-quality",
  "rubricVersion": "v1",
  "judgeModel": "gpt-5-mini",
  "judgeVersion": "2026-07-05",
  "score": 0.84,
  "confidence": 0.78,
  "rationaleSummary": "Answer is complete but misses one coaching step.",
  "disagreementMarkers": [],
  "isBlocking": false
}
```

Rules:

- `isBlocking` must be false unless the rubric is blocking-enabled.
- Rationale summaries must not contain operational secrets.
- Full AI payloads may be present in LangSmith under an approved full-content
  policy, but local report summaries should remain concise.

## Export Policy Decision

```json
{
  "decisionId": "epd_01J...",
  "destination": "LANGSMITH",
  "environment": "PRODUCTION",
  "representationLevel": "FULL_CONTENT",
  "policyVersion": "production-langsmith-full-content-v1",
  "owner": "ai-platform",
  "accessScope": "ai-ops-debuggers",
  "retentionDays": 30,
  "result": "PASSED"
}
```

Rules:

- A production full-content LangSmith sync must include an export policy
  decision.
- Non-approved destinations must not receive raw AI payloads.
- Operational secrets are never valid content.

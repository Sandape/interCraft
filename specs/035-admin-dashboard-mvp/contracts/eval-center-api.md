# Eval Center API Contract

Base path: `/api/v1/admin-console/eval-center`

All endpoints require `EVAL_VIEW`.

## GET `/runs`

Lists eval runs with score, cost, token, and trace-link summary.

Query:

| Parameter | Description |
|---|---|
| `suite` | Eval suite, for example `golden` or `nightly`. |
| `environment` | ci/staging/local/production-like. |
| `source_revision` | Code revision. |
| `prompt_version` | Prompt version/fingerprint. |
| `rubric_version` | Rubric version. |
| `model` | Model under test or judge model. |
| `status` | `passed`, `failed`, `incomplete`, `overridden`. |
| `date_from`, `date_to` | Time range. |
| `limit`, `cursor` | Pagination. |

Response 200:

```json
{
  "items": [
    {
      "eval_run_id": "eval_019ef...",
      "suite": "golden",
      "environment": "ci",
      "dataset_id": "golden-v1",
      "source_revision": "abc1234",
      "prompt_version": "prompt_a",
      "rubric_version": "rubric_v1",
      "model": "deepseek-v4-pro",
      "status": "failed",
      "pass_rate": 0.92,
      "avg_score": 0.81,
      "failed_case_count": 2,
      "total_tokens": 14200,
      "estimated_cost": 0.053,
      "started_at": "2026-06-29T12:00:00Z",
      "completed_at": "2026-06-29T12:02:00Z"
    }
  ],
  "next_cursor": null
}
```

## GET `/runs/{eval_run_id}`

Returns one eval run and case summaries.

Response 200:

```json
{
  "eval_run": {
    "eval_run_id": "eval_019ef...",
    "suite": "golden",
    "status": "failed",
    "pass_rate": 0.92,
    "avg_score": 0.81
  },
  "cases": [
    {
      "case_result_id": "case_result_1",
      "case_id": "golden_resume_001",
      "status": "failed",
      "score": 0.4,
      "score_dimensions": {
        "task_success": 0.0,
        "format_validity": 1.0,
        "safety": 1.0
      },
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "badcase_id": "badcase_1",
      "failure_reason": "Expected suggestion category missing"
    }
  ]
}
```

## GET `/cases/{case_result_id}`

Returns eval case detail.

Response 200:

```json
{
  "case_result_id": "case_result_1",
  "case_id": "golden_resume_001",
  "status": "failed",
  "score": 0.4,
  "score_dimensions": {
    "task_success": 0.0,
    "format_validity": 1.0,
    "safety": 1.0,
    "privacy_leakage": 1.0,
    "tool_call_correctness": null
  },
  "expected_summary": "Resume diagnosis should identify missing quantified impact.",
  "actual_summary": "Output omitted the missing impact category.",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "llm_call_id": "llm_1",
  "badcase_id": "badcase_1",
  "evaluator": {
    "evaluator_id": "rubric_resume_v1",
    "type": "rubric",
    "rubric_version": "rubric_v1",
    "judge_prompt_version": "judge_v1"
  }
}
```

## GET `/gate/latest`

Returns latest eval gate state.

Response 200:

```json
{
  "gate": "pr_eval",
  "status": "failed",
  "eval_run_id": "eval_019ef...",
  "source_revision": "abc1234",
  "failed_case_count": 2,
  "override": {
    "status": "none",
    "pm_approver": null,
    "technical_approver": null
  }
}
```

## Metric Dimensions

Eval Center must display or record:

- Task success / pass rate.
- Rubric score and per-dimension scores.
- Format/schema validity.
- Safety and privacy leakage.
- Tool-call correctness where applicable.
- Human-review agreement where available.
- Stability across repeated runs where available.
- Cost, tokens, latency, timeout rate.
- Regression delta against baseline.
- Links to trace, node, LLM call, badcase, prompt version, rubric version, and
  model.

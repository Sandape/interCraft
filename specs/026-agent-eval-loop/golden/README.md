# Golden Dataset — Feature 026 Eval Suite

This directory holds the version-controlled golden cases for the agent eval
suite (spec FR-006/007/008). Each case is a JSON file describing one
(node, input_state, llm_response, expected) tuple.

## Directory Layout

```
golden/
├── interview_score/      # 5 cases for interview.score node
│   ├── case_01_high_chinese.json
│   ├── case_02_mid_chinese.json
│   ├── case_03_low_chinese.json
│   ├── case_04_english_regression.json   # known-bad: zh-CN prompt → English feedback
│   └── case_05_short_answer.json
└── interview_report/     # 5 cases for interview.report node
    ├── case_01_strong_chinese.json
    ├── case_02_weak_chinese.json
    ├── case_03_mixed_chinese.json
    ├── case_04_english_regression.json   # known-bad: zh-CN prompt → English summary_md
    └── case_05_minimal_scores.json
```

## Case Schema

Each JSON file must have these fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `case_id` | string | yes | Unique identifier (used for dedup + pytest parametrize). |
| `node` | string | yes | Graph node identifier — `interview.score` / `interview.report` / etc. |
| `label` | string | yes | Human-readable description of what this case tests. |
| `source` | string | yes | `manual` (authored) or `promoted` (from production trace). |
| `input_state` | object | yes | Graph state dict fed to the node function. |
| `llm_response` | string | yes | Raw LLM output content (the JSON string the node parses). |
| `expected_language` | string | no | Prompt's required language (default `"zh-CN"`). |
| `expected_contains` | string[] | no | Keywords that should appear in the parsed output. |
| `expected_score_range` | [int, int] | no | Inclusive range — for `interview.score` node. |
| `expected_overall_score_range` | [float, float] | no | Inclusive range — for `interview.report` node. |
| `expected_fidelity_pass` | bool | no | Default `true`. Set `false` for regression cases where the LLM produces English output — the eval suite validates that the checker correctly flags it. |
| `status` | string | no | `active` (default) or `stale` (skipped from metrics). |

## Adding a New Case

1. Pick the right subdirectory (`interview_score/`, `interview_report/`, or
   a new `<graph>_<node>/` dir).
2. Copy an existing case file as a template.
3. Update `case_id` (must be unique across all cases).
4. Set `input_state` to match the node's expected state shape — see
   `backend/app/agents/interview/state.py` for `InterviewGraphState`.
5. Set `llm_response` to the LLM's raw output (the JSON string).
6. Set `expected_*` fields to validate the node's parsing result.
7. For regression cases: set `expected_fidelity_pass: false` to validate the
   checker catches the regression.
8. The new case is automatically picked up by the next eval run — no
   registration needed (FR-008).

## Marking a Case Stale

When a state schema change breaks a case, set `"status": "stale"`. Stale cases
are loaded but excluded from metrics (per spec edge case: "stale case is
flagged and excluded from metrics, not silently dropped"). The aggregate
report includes them in `skipped_cases`.

## Production Trace Promotion

Cases with `source: "promoted"` come from real production traces via the
US5 self-evolution workflow (not yet implemented — deferred to US5).

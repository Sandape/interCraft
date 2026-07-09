# Judge Calibration Labels

REQ-045 judge gating is report-only until calibration evidence exists.

## Label Shape

```json
[
  {
    "case_id": "case-001",
    "human_passed": true,
    "judge_passed": true,
    "notes": "Human and judge agree on task success."
  }
]
```

## Blocking Rule

- At least 30 human-labeled examples.
- Agreement rate at or above 0.80.
- A temporary waiver may enable blocking, but the waiver reason must be recorded.

Without calibration or waiver, judge output is evidence-only and must not block
merge or production rollout.

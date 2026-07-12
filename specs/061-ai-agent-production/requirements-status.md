# REQ-061 Requirements Status

| Slice | Status | Notes |
|---|---|---|
| Foundation + US1-US12 implementation tasks | done | See `tasks.md` - all `[X]` |
| Aggregate gate T167-T182 | done | Skeletons + evidence templates; live drill evidence still pending where noted |
| T183 LangGraph upgrade | done | Closed 2026-07-12 (`32a08f4`); migrated to `langgraph==1.2.9` + `langgraph-checkpoint-postgres==3.1.0`; STRICT_MSGPACK enabled; evidence in `docs/evidence/061-ai-agent-production/langgraph-support-migration.md` |
| Eval fixture expansion (US11 T144) | done | 13 to 450 active cases via `backend/tests/eval/_gen`; meets_fr112=True; hardened in `tests/eval/test_061_eval_dataset_coverage.py` + `test_061_evaluator_calibration.py`; evidence in `docs/evidence/061-ai-agent-production/eval-fixture-expansion.md` |

Aggregate production release gate (Final Checkpoint) is now ready to schedule.
T144 + T183 no longer block - capability cutover remains gated by the live
verification of the US11 evaluation gate against real model outputs in
`docs/evidence/061-ai-agent-production/quickstart-validation.md`.

# REQ-061 Requirements Status

| Slice | Status | Notes |
|---|---|---|
| Foundation + US1-US12 implementation tasks | in_progress (partial) | See `tasks.md` — US6 tasks T091/T092/T096/T099 remain unchecked |
| Aggregate gate T167-T182 | done | Skeletons + evidence templates; live drill evidence still pending where noted |
| T183 LangGraph upgrade | done | Closed 2026-07-12 (`32a08f4`); migrated to `langgraph==1.2.9` + `langgraph-checkpoint-postgres==3.1.0`; STRICT_MSGPACK enabled; evidence in `docs/evidence/061-ai-agent-production/langgraph-support-migration.md` |
| Eval fixture expansion (US11 T144) | done | 450 active cases via fully programmatic `backend/tests/eval/_gen`; meets_fr112=True; hardened in `tests/eval/test_061_eval_dataset_coverage.py` + `test_061_evaluator_calibration.py`; evidence in `docs/evidence/061-ai-agent-production/eval-fixture-expansion.md` |
| US6 profile/research canonical task (T091/T092/T094/T096/T097/T099) | in_progress | 2026-07-13 codex/064: T094 cites dashboard contract — typed `verified_score_status` (`"ready"|"unavailable"`) and `AbilityInsightProjection` (`task_id` field); service queries canonical AITask ordered by `accepted_at DESC, id DESC` with owner isolation; score 0 from interview/coach qualifies as ready. T097 cites frontend typed consumption — pages consume `DashboardResponse` fields directly with no `any`/`@ts-ignore`/double assertions or fabricated ready fallback. T091/T092/T099 remain unchecked. T092 integration test file now exists but remains incomplete: local 10/10 tests are unverified/skipped without PostgreSQL and research pre-opt-in point behavior is not covered. T096 remains unchecked (neither worker is connected to the canonical lifecycle; zero-point lifecycle/settlement/fencing gaps deferred to a follow-up governed Issue). |

Aggregate production release gate (Final Checkpoint) is **not** ready — US6 is still in_progress with T091/T092/T096/T099 unchecked. Completion is gated on live verification evidence for all stories, the US11 evaluation gate against real model outputs, and resolution of all open US6 tasks.

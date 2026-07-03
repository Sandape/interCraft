# Observability (REQ-029 / REQ-040 US2)

OpenTelemetry tracing library + LangGraph node coverage matrix.

## US2 Node → Span Name Mapping (AC-E2E-4)

After REQ-040 US2 FR-003/FR-006, every LangGraph leaf node carries an
`@traced_node("{agent}.{role}_{action}")` decorator. The OTel span
name is `node.{agent}.{role}_{action}` (single `node.` prefix — the
decorator adds it). The `interview_planner` subgraph registration is
NOT prefixed (per US2 R3''' P1).

| Agent | Node file | Function | Span name |
|-------|-----------|----------|-----------|
| interview | interview/nodes/intake.py | intake_node | `node.interview.intake_locate` |
| interview | interview/nodes/question_gen.py | question_gen_node | `node.interview.question_gen` |
| interview | interview/nodes/score_llm.py | score_llm_node | `node.interview.score_llm` |
| interview | interview/nodes/sink_error.py | sink_error_node | `node.interview.sink_error` |
| interview | interview/nodes/report.py | report_node | `node.interview.report` |
| interview | interview/planner_graph.py | _passthrough_node (subgraph) | (not decorated; subgraph) |
| ability_diagnose | nodes/ability_diagnose/aggregate_scores.py | aggregate_scores_node | `node.ability_diagnose.aggregate_scores` |
| ability_diagnose | nodes/ability_diagnose/compare_baseline.py | compare_baseline_node | `node.ability_diagnose.compare_baseline` |
| ability_diagnose | nodes/ability_diagnose/generate_insight.py | generate_insight_node | `node.ability_diagnose.generate_insight` |
| ability_diagnose | nodes/ability_diagnose/update_dim_db.py | update_dim_db_node | `node.ability_diagnose.update_dim_db` |
| ability_diagnose | nodes/ability_diagnose/update_history.py | update_history_node | `node.ability_diagnose.update_history` |
| ability_diagnose | nodes/ability_diagnose/update_activities.py | update_activities_node | `node.ability_diagnose.update_activities` |
| ability_diagnose | nodes/ability_diagnose/ws_push.py | ws_push_node | `node.ability_diagnose.ws_push` |
| ability_diagnose | nodes/ability_diagnose/update_dim_error_log.py | update_dim_error_log_node | `node.ability_diagnose.update_dim_error_log` |
| error_coach | nodes/error_coach/fetch_question.py | fetch_question_node | `node.error_coach.fetch_question` |
| error_coach | nodes/error_coach/hint_ladder.py | hint_ladder_node | `node.error_coach.hint_ladder` |
| error_coach | nodes/error_coach/evaluate.py | evaluate_node | `node.error_coach.evaluate` |
| error_coach | nodes/error_coach/loop_or_finish.py | loop_or_finish_node | `node.error_coach.loop_or_finish` |
| general_coach | nodes/general_coach/intent.py | intent_node | `node.general_coach.intent` |
| general_coach | nodes/general_coach/route.py | route_node | `node.general_coach.route` |
| general_coach | nodes/general_coach/respond.py | respond_node | `node.general_coach.respond` |
| resume_optimize | nodes/resume_optimize/load_branch.py | load_branch_node | `node.resume_optimize.load_branch` |
| resume_optimize | nodes/resume_optimize/diff_jd.py | diff_jd_node | `node.resume_optimize.diff_jd` |
| resume_optimize | nodes/resume_optimize/suggest_blocks.py | suggest_blocks_node | `node.resume_optimize.suggest_blocks` |
| resume_optimize | nodes/resume_optimize/apply_or_discard.py | apply_or_discard_node | `node.resume_optimize.apply_or_discard` |
| resume_optimize | nodes/resume_optimize/snapshot.py | snapshot_node | `node.resume_optimize.snapshot` |

**Coverage baseline (AC-6.1):** 25 leaf-node functions decorated with
`@traced_node`, plus the planner subgraph (registered as
`interview_planner` without a prefix). AC-6.1's verification target
counts the 25 leaf functions.

## FR-006: Node split rationale

- **interview.score → score_llm + sink_error** (FR-004). LLM
  evaluation and DB write are independent concerns; splitting allows
  each to fail and retry in isolation.
- **ability_diagnose.update_dimensions → 4 + 1** (FR-005). The legacy
  single function mixed `ability_dimensions` UPSERT, history append,
  activity insert, and WS push — splitting into `update_dim_db`,
  `update_history`, `update_activities`, `ws_push` plus an intermediate
  `update_dim_error_log` for `db_warnings` logging (AC-5.7).
- **`@traced_node` 100% coverage** of leaf nodes (FR-006). Every leaf
  function is decorated; the planner subgraph's `_passthrough_node` is
  intentionally NOT decorated because it is a no-op stub for the 032 v2
  MVP (per US2 R3''' P1).

## Cross-REQ handoff (REQ-043 US-1)

REQ-043 US-1 consumes the span names above to drive LangSmith trace
grouping + observability dashboards. The `{agent}.{role}_{action}`
naming convention allows REQ-043 to filter / aggregate by agent and by
role without parsing span attributes.

## Tests

- `app/agents/tests/test_traced_node_coverage.py` — verifies 100%
  coverage, span name format, and ERROR-marking on exceptions.
- `app/agents/tests/test_node_separation.py` — verifies score split
  (FR-004), update_dimensions split (FR-005), and the related routing
  / state schema additions.
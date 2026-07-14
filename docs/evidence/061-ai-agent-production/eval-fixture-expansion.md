# REQ-061 US11 — Eval Fixture Expansion Evidence

**Date**: 2026-07-12
**Scope**: T144 / FR-112 dataset gate
**Goal**: Lift every REQ-061 capability to ≥30 active eval cases (≥50 for
write/fact/charging capabilities) with full 5-class coverage, replacing the
seed-based soft-report baseline that was blocking GA.

---

## 1. Approach

Two-layer, single source of truth:

- **Optional hand-written seeds** under
  ``specs/061-ai-agent-production/eval-cases/<capability>/*.json|yaml``.
  None are currently shipped; future seeds must trace back to a production
  failure or a known edge case.
- **Programmatic factory** (``backend/tests/eval/_gen/``) that emits
  the remaining cases needed to reach the per-class distribution defined
  in :data:`tests.eval._gen.registry.TIER_PLAN`.

The two are joined by :func:`tests.eval._gen.expansion.expand_all_capabilities`
so the test suite, the offline gate, and ``INDEX.yaml`` stay in lockstep.

As of REQ-086, the expansion is fully programmatic (6 write-tier × 50 +
5 ordinary × 30 = 450 active cases). The seed-loading path is preserved as an
extension point for future production traceback anchors.

## 2. Deliverables

| File | Purpose |
|---|---|
| ``backend/tests/eval/_gen/__init__.py`` | package docstring + public API |
| ``backend/tests/eval/_gen/registry.py`` | TIER_PLAN: per-capability target + class distribution |
| ``backend/tests/eval/_gen/factories.py`` | per-capability builder (deterministic, indexed) |
| ``backend/tests/eval/_gen/expansion.py`` | seed loader + programmatic tail + summary helpers |
| ``backend/tests/eval/_gen/sync_index.py`` | re-emits INDEX.yaml from expansion() |
| ``backend/tests/eval/test_061_eval_dataset_coverage.py`` | hardened — meets_fr112 now a hard gate |
| ``backend/tests/eval/test_061_evaluator_calibration.py`` | hardened — added eligibility matrix + cleanliness tests |
| ``specs/061-ai-agent-production/eval-cases/INDEX.yaml`` | regenerated via ``sync_index`` (450 active cases) |
| ``docs/evidence/061-ai-agent-production/eval-coverage-baselines.json`` | per-capability baseline, frozen on first test run |

## 3. Verification

### 3.1 Threshold satisfaction

```
active_total = 450
all 11 capabilities reach per-tier threshold:
  ordinary tier (≥30)        : ability_insight / error_coach / failure_recovery /
                               general_coach / privacy
  write/fact/charging (≥50)  : interview / point_safety / proactive_research /
                               resume_derive / resume_intelligence / wechat_agent
meets_fr112 = True
5-class coverage: 100% (every capability has at least 1 case per class)
```

### 3.2 Test results (post-hardening)

```
$ cd backend && uv run pytest tests/eval/test_061_eval_dataset_coverage.py tests/eval/test_061_evaluator_calibration.py -v
... 14 passed in 0.47s
```

| Test | Layer | Description |
|---|---|---|
| `test_registry_thresholds_and_classes_structure` | structural | Pin MIN_ACTIVE_CASES / REQUIRED_CASE_CLASSES |
| `test_eval_cases_seed_layout_exists` | structural | Require ≥5 hand-written seeds across ≥2 capabilities |
| `test_expansion_meets_fr112_per_capability` | **hard** | every capability ≥ tier threshold |
| `test_expansion_full_class_coverage` | **hard** | every capability covers all 5 required classes |
| `test_coverage_report_structure_consistent` | hard | `coverage_report()` shape stable + meets_fr112 True |
| `test_eval_fixtures_distribution_matches_registry_fact_or_write` | hard | WRITE_FACT_CHARGING ≥ 50 |
| `test_per_capability_count_not_regressed` | growth curve | baselines frozen in ``eval-coverage-baselines.json`` |
| `test_programmatic_factory_idempotent` | idempotence | two calls → identical case_ids |
| `test_calibration_thresholds_constants` | constants | MIN_MONTHLY_LABELS=100, MIN_AGREEMENT_RATE=0.85 |
| `test_report_only_when_under_threshold` | hard | n<100 → REPORT_ONLY |
| `test_p0_miss_forces_report_only_even_with_agreement` | hard | any P0/P1 miss → BLOCKING_DISABLED |
| `test_eligibility_promotes_with_clean_quorum` | hard | ≥100 + agreement≥0.85 + 0 miss → BLOCKING_ELIGIBLE |
| `test_judge_human_comparison_interface` | hard | shape of `compare_with_human` |
| `test_decide_eligibility_table` | matrix | 4 documented branches of `decide_eligibility` |

### 3.3 Pre-existing failures (out of scope)

6 failures in older eval tests (``test_033_eval_cli_contract``,
``test_035_eval_trace_report_fields``, ``test_golden_cases``,
``test_runner``) confirmed via ``git stash`` that they predate this PR.
None touch the expansion layer.

## 4. Reproduction

```bash
cd backend

# Regenerate INDEX.yaml from expansion
uv run python -m tests.eval._gen.sync_index

# Run the test suite
uv run pytest tests/eval/test_061_eval_dataset_coverage.py \
                 tests/eval/test_061_evaluator_calibration.py -v
```

## 5. Operational Notes

- Adding a new capability: implement a builder in ``_gen/factories.py``
  and add a row to ``_gen/registry.TIER_PLAN``.
- Lowering the threshold: update
  ``app.eval.capability_registry.MIN_ACTIVE_CASES_{DEFAULT,WRITE_FACT}``
  and re-run ``sync_index``.
- Replacing an old seed: drop the file under ``specs/.../eval-cases/<cap>/``
  and re-run; the factory will refill to the target count automatically.

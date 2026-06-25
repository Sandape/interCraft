# Tasks: REQ-030 IRT-Based Adaptive Ability Diagnosis

**Input**: Design documents from `specs/030-irt-adaptive-diagnosis/`
(plan.md, spec.md, data-model.md in this dir, contracts/irt-api.md).

**Scope**: US1 only (item bank + 2-PL IRT + θ estimation).
US2/US3/US4 + 3-PL are listed but **⏳ deferred** — see "Phase N+ Deferrals"
at the end.

**Constitution gates**: Library-First (self-contained `app/modules/irt/`),
Test-First (math tests before implementation), CLI Interface
(`irt_estimate_theta` script), Observability (structlog events).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4)
- File paths absolute from `D:\Project\eGGG\`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and module skeleton.

- [X] T001 [US1] Create IRT module directory + `__init__.py` with public re-exports at `D:\Project\eGGG\backend\app\modules\irt\__init__.py`
- [X] T002 [P] [US1] Create IRT `tests/` package + `__init__.py` at `D:\Project\eGGG\backend\app\modules\irt\tests\__init__.py`

**Checkpoint**: Module skeleton present; public API surface defined in `__init__.py`.

## Phase 2: Foundational (Math Library + Storage)

**Purpose**: Core math engine (2-PL probability + Newton-Raphson θ) and
storage layer (models + Alembic migration). **Blocks all US1 implementation.**

**⚠️ CRITICAL**: No US1 task can start until Phase 2 is complete.

- [X] T003 [US1] Implement `engine.py` at `D:\Project\eGGG\backend\app\modules\irt\engine.py` with:
  - `probability_2pl(theta: float, a: float, b: float) -> float` (P = sigmoid(a(θ-b)))
  - `log_likelihood(theta, responses) -> float` (binary correct/incorrect)
  - `gradient(theta, responses) -> float` (closed-form dℓ/dθ)
  - `hessian(theta, responses) -> float` (closed-form d²ℓ/dθ²)
  - `estimate_theta_mle(responses, items, *, max_iter=25, tol=0.01) -> ThetaResult`
  - All clamp P to [ε, 1-ε] (ε=1e-9) to guard log(0) at all-correct/all-incorrect edges
  - Zero-discrimination items (a≈0) skipped in gradient/hessian sum
  - structlog events: `irt.engine.theta_estimated` (on success), `irt.engine.convergence_failed` (on max_iter)
- [X] T004 [P] [US1] Define Pydantic schemas at `D:\Project\eGGG\backend\app\modules\irt\schemas.py`:
  - `ItemOut` (id, dimension, difficulty_b, discrimination_a, model, status, response_count, standard_error, last_calibrated_at)
  - `ItemResponseIn` (item_id, response, score, source_interview_id)
  - `ThetaResult` (theta, standard_error, n_items, converged, iterations)
  - `ItemCreate` (dimension, question_text_hash, difficulty_b, discrimination_a, model, status)
- [X] T005 [US1] Create Alembic migration `0020_irt_item_bank.py` at `D:\Project\eGGG\backend\migrations\versions\0020_irt_item_bank.py`:
  - `irt_items` table (no RLS, shared bank) with CHECK constraints on status/model/difficulty/discrimination
  - `irt_item_responses` table (RLS user-scoped) with item_id ON DELETE SET NULL
  - `irt_ability_thetas` table (RLS user-scoped)
  - Partial unique index on `(dimension, question_text_hash) WHERE status != 'retired'`
  - RLS policies on the two user-scoped tables mirroring `agent_memory` 0018 pattern
  - Indexes: `idx_irt_items_dimension_status`, `idx_irt_responses_user_dim`, `idx_irt_thetas_user_dim`
- [X] T006 [US1] Implement SQLAlchemy models at `D:\Project\eGGG\backend\app\modules\irt\models.py`:
  - `Item` (id, dimension, question_text_hash, difficulty_b, discrimination_a, model, status, response_count, standard_error, last_calibrated_at, created_at, updated_at)
  - `ItemResponse` (id, user_id, item_id, response, score, source_interview_id, created_at)
  - `AbilityTheta` (id, user_id, dimension, theta, standard_error, n_items, source_interview_id, model, converged, created_at)

**Checkpoint**: Migration applies cleanly; ORM models importable; math engine
solves known ground truth (verified by Phase 3 tests).

## Phase 3: User Story 1 - Item Bank + 2-PL + θ Estimation (Priority: P1) 🎯 MVP

**Goal**: Self-contained IRT module that loads seed items, estimates θ from
binary responses via Newton-Raphson MLE, and integrates with the existing
`ability_diagnose` graph as a non-replacing sidecar.

**Independent Test**: Given 5–10 mock binary responses to seeded items,
`estimate_theta_mle` returns θ̂ with error < 0.3 logits vs. ground truth
(known (a, b) parameters with simulated responses from θ=0).

### Tests for User Story 1 (Test-First per Constitution III)

> **NOTE: Written FIRST, verified FAIL before implementation (T007, T008, T009)**

- [X] T007 [P] [US1] Unit tests for 2-PL probability at `D:\Project\eGGG\backend\tests\unit\test_irt_engine.py::TestProbability2PL`:
  - `test_probability_at_difficulty_is_half` — P(b; a=1, b=0) == 0.5 ± 1e-9
  - `test_probability_high_theta_approaches_one` — P(θ=10; a=1, b=0) > 0.9999
  - `test_probability_low_theta_approaches_zero` — P(θ=-10; a=1, b=0) < 1e-6
  - `test_probability_monotonic_in_theta` — P(θ_i) ≤ P(θ_{i+1}) for θ_i ascending
  - `test_probability_higher_discrimination_steeper` — P(θ=1; a=2, b=0) > P(θ=1; a=1, b=0)
  - `test_probability_symmetric_around_b` — P(b+d) + P(b-d) ≈ 1 (for finite d)
- [X] T008 [P] [US1] Unit tests for θ estimation at `D:\Project\eGGG\backend\tests\unit\test_irt_engine.py::TestEstimateThetaMLE`:
  - `test_estimate_theta_zero_with_balanced_correct` — known (a=1, b=0) × 5 items, all answered correctly → θ̂ > 1.0 (high)
  - `test_estimate_theta_zero_with_balanced_incorrect` — same items, all wrong → θ̂ < -1.0 (low)
  - `test_estimate_theta_recovers_ground_truth` — generate 20 responses with known (a=1, b=0.5) and θ=1.0; estimate |θ̂ - 1.0| < 0.3
  - `test_estimate_theta_converges_within_max_iter` — `converged=True`, `iterations <= 25`
  - `test_estimate_theta_zero_items_returns_neutral` — empty responses → θ̂=0.0, n_items=0, converged=True
  - `test_estimate_theta_all_correct_does_not_overflow` — 5 items all correct → returns valid θ, no NaN/Inf
  - `test_estimate_theta_all_incorrect_does_not_overflow` — 5 items all incorrect → returns valid θ, no NaN/Inf
  - `test_standard_error_decreases_with_more_items` — SE(5 items) > SE(20 items)
  - `test_seed_loader_produces_ten_items_per_dimension` — for each of 5 dimensions, seed produces exactly 10 items
- [X] T009 [P] [US1] Integration test at `D:\Project\eGGG\backend\tests\integration\test_ability_diagnose_irt.py`:
  - Insert 10 seed items for `tech_depth` via repository
  - Insert 5 ItemResponse rows (3 correct, 2 incorrect) for a test user
  - Call aggregate_scores_node with mocked query_interview_* helpers
  - Assert output contains `irt_theta` list with one entry per dimension that had responses
  - Assert each entry has `dimension`, `theta` (float, |theta| <= 6), `standard_error` (float, > 0), `n_items` (int, == 5)

### Implementation for User Story 1

- [X] T010 [P] [US1] Seed loader at `D:\Project\eGGG\backend\app\modules\irt\seed.py`:
  - `SEED_ITEMS_PER_DIMENSION: dict[str, list[dict]]` — hardcoded 10 items per dimension (tech_depth, architecture, engineering_practice, communication, algorithm) with `difficulty_b` spanning [-2, 2] and `discrimination_a` in [0.8, 1.5]
  - `seed_items_for_dimension(dim: str) -> list[ItemCreate]`
  - `seed_all_dimensions() -> list[ItemCreate]` (5 × 10 = 50 items)
- [X] T011 [US1] Repository at `D:\Project\eGGG\backend\app\modules\irt\repository.py`:
  - `ItemRepository.upsert_seed_items(items: list[ItemCreate]) -> int` (returns count)
  - `ItemRepository.list_for_dimension(dim: str, *, status: str | None = "calibrated") -> list[Item]`
  - `ItemRepository.list_calibrated(dimension: str, limit: int) -> list[Item]`
  - `ItemRepository.get_by_id(item_id: UUID) -> Item | None`
  - `ItemResponseRepository.insert_response(user_id, item_id, response, score, source_interview_id) -> ItemResponse`
  - `ItemResponseRepository.list_for_user(user_id, dimension: str, since: datetime | None = None) -> list[ItemResponse]`
  - `AbilityThetaRepository.insert(user_id, dimension, theta, se, n_items, source_interview_id, model, converged) -> AbilityTheta`
  - `AbilityThetaRepository.list_for_user(user_id, dimension: str | None = None, limit: int = 50) -> list[AbilityTheta]`
- [X] T012 [US1] CLI entry at `D:\Project\eGGG\backend\app\modules\irt\cli.py`:
  - `estimate-theta --user-id <uuid> --dimension <key>` — print `theta=<float> se=<float> n_items=<int> converged=<bool>` to stdout
  - `seed-items [--reset]` — call `seed_all_dimensions()` and `ItemRepository.upsert_seed_items`
  - `list-items --dimension <key> [--status <status>]` — JSON output of items
  - Errors to stderr; `--help` shows usage
- [X] T013 [US1] Standalone script wrapper at `D:\Project\eGGG\backend\scripts\irt_estimate_theta.py` enabling `python -m scripts.irt_estimate_theta ...`
- [X] T014 [US1] Update `aggregate_scores_node` at `D:\Project\eGGG\backend\app\agents\nodes\ability_diagnose\aggregate_scores.py`:
  - After computing `interview_scores` (existing weighted-avg path), **additive** sidecar: query `ItemResponseRepository` for the user since session start, group by dimension, estimate θ per dimension via `estimate_theta_mle`, and append to output as `irt_thetas: list[dict]` (one entry per dimension with `dimension`, `theta`, `standard_error`, `n_items`, `converged`)
  - On math error (no items / all-zero discriminators), log `irt.engine.skipped` and emit `irt_thetas: []` — never breaks the existing path
  - Does NOT touch `interview_scores` shape; backward compatible
- [X] T015 [US1] Module README at `D:\Project\eGGG\backend\app\modules\irt\README.md`:
  - Overview + 2-PL vs 3-PL rationale (US1 ships 2-PL only; 3-PL deferred)
  - Math formulation (P(θ), log-likelihood, gradient, Hessian, Newton-Raphson)
  - Public API (engine, schemas, repository)
  - CLI usage examples
  - Item bank lifecycle (US1 hardcoded seeds; US3 production calibration)
  - RLS note (items global; responses + thetas user-scoped)

**Checkpoint**: US1 fully functional and independently testable. Existing
`ability_diagnose` graph output is backward-compatible (new `irt_thetas` key
additive, old `interview_scores` unchanged).

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and validation.

- [X] T016 [P] [US1] Update `D:\Project\eGGG\specs\README.md` row 030 status: `in_progress (US1 partial)` with note "item bank + 2-PL + θ estimation; US2/3/4 + 3-PL deferred"
- [X] T017 [P] [US1] Write `D:\Project\eGGG\specs\030-irt-adaptive-diagnosis\requirements-status.md` with FR/SC mapping; mark US1 FRs done, US2/3/4 ⏳ deferred
- [X] T018 [US1] Run ruff check on new module: `uv run ruff check app/modules/irt/ tests/unit/test_irt_engine.py tests/integration/test_ability_diagnose_irt.py` (auto-fix then manual for the rest)
- [X] T019 [US1] Run mypy on new module: `uv run mypy app/modules/irt/ --strict` (target: clean; use `result: Any = ...` + `type: ignore[no-any-return]` patterns from 029 lessons if needed)
- [X] T020 [US1] Run full backend test suite: `cd backend && uv run pytest -q` — confirm 0 regression vs. baseline (617 tests pass; +N new IRT tests)

**Checkpoint**: All Phase 4 done. US1 ready for review.

---

## Phase 5+ Deferrals (NOT Implemented in This Cycle)

> **⏳ All tasks in this section are explicitly deferred.** They are listed
> for traceability to the spec, but **not implemented** in this REQ cycle.
> See plan.md "Scope Decision" for the rationale (US2/3/4 require real
> calibrated parameters + graph refactor + ARQ calibration batch — too
> much surface area for a single cycle given L004 api-quota-risk).

### Phase 5: US2 - Adaptive Question Selection (P2) ⏳ DEFERRED

- [ ] T101 [US2] `ItemSelector` with information-gain maximization (D-optimal)
- [ ] T102 [US2] `ability_diagnose` graph branch: adaptive-mode opt-in
- [ ] T103 [US2] Confidence-interval-aware question selection (target ±0.5 logits of running θ̂)
- [ ] T104 [US2] Fallback to uncalibrated items with prior estimates when bank exhausted
- [ ] T105 [US2] US2 contract test: ≥70% of selections within ±0.5 logits of current θ̂

### Phase 6: US3 - Item Bank Maintenance (P3) ⏳ DEFERRED

- [ ] T201 [US3] `CalibrationRun` table populated by offline batch
- [ ] T202 [US3] ARQ `calibrate_items` task with retry wrapper (L001: must use `retry_graph_op` or inline equivalent if any graph ops involved)
- [ ] T203 [US3] Items with <30 responses → marked `uncalibrated`; ≥30 → run MML calibration
- [ ] T204 [US3] Discrimination `a < 0.3` → flag for review
- [ ] T205 [US3] Bank health dashboard endpoint (per-dim calibrated/uncalibrated/retired counts)
- [ ] T206 [US3] Drift detection across calibration runs (parameter delta > threshold → flagged)

### Phase 7: US4 - Adaptive Mode as Interview Opt-In (P3) ⏳ DEFERRED

- [ ] T301 [US4] Interview graph: new branch for "diagnostic_mode" (parallel to existing 5-question fixed)
- [ ] T302 [US4] `interview_sessions` new column `mode: TEXT` (`mock` / `diagnostic`)
- [ ] T303 [US4] Adaptive question picker wired into `interview.question_gen` node
- [ ] T304 [US4] Frontend Interview setup: toggle "Mock interview (5 questions) / Diagnostic mode (adaptive)"
- [ ] T305 [US4] E2E: `tests/e2e/round-3/interview-diagnostic-mode.spec.ts` (deterministic via MockLLMClient)

### Phase 8: 3-PL + Production Validation ⏳ DEFERRED

- [ ] T401 3-PL guessing parameter `c` in IRF; theta estimation extended for 3-PL
- [ ] T402 Retest reliability measured on production data: SC-002 ≥0.85 per dimension
- [ ] T403 Replace `aggregate_scores` weighted-average with θ (gated on T402)

---

## Dependencies & Execution Order

```
Phase 1 (Setup) ──→ Phase 2 (Math + Storage) ──→ Phase 3 (US1)
                                                  │
                                                  ├── T007/T008/T009 tests first (fail)
                                                  ├── T010-T015 implementation
                                                  └── T009 integration test (pass)
                                                  │
                                                  ▼
                                              Phase 4 (Polish)
                                                  │
                                                  ├── T016-T017 docs
                                                  ├── T018-T019 lint/typecheck
                                                  └── T020 full regression
```

### Within Each Phase
- Tests (T007, T008, T009) **written before** corresponding implementation
- Math (T003) before repository (T011) before aggregate_scores integration (T014)
- Migration (T005) before any repository method that depends on the schema

### Parallel Opportunities
- T003 (engine), T004 (schemas), T005 (migration), T006 (models) can run
  in parallel — different files, no dependencies
- T007, T008 unit tests in same file but different `Test*` classes
- T010 (seed), T011 (repository) can run in parallel after T004+T006

## Implementation Strategy

### MVP First (US1 Only)
1. Phase 1 (Setup)
2. Phase 2 (Math + Storage) — TDD on engine first
3. Phase 3 (US1 implementation + integration test)
4. Phase 4 (Polish + docs + full regression)
5. **STOP**. US2/3/4 explicitly deferred to next cycle.

### Why partial_implementation=true
- L004 (api-quota-risk) recurred in 027/028/029; per spec, this REQ runs
  US1 only to keep LLM call surface small (IRT math is pure-Python; zero
  LLM calls).
- US2 requires interview graph refactor (LangGraph interrupt + state
  reshape); out of scope for this cycle.
- US3 requires offline ARQ calibration batch over production data; needs
  US1 to be stable first.
- US4 depends on US2 (adaptive picker must exist first).

## Notes

- T007/T008 ground truth: items with `(a=1.0, b=0.0)` and balanced responses
  → θ̂ ≈ 0.0 (error < 0.3 logit per spec acceptance).
- Pure-Python Newton-Raphson chosen over scipy.optimize to avoid new
  dependencies (project pattern: 028 agent_memory, 029 observability
  shipped with zero new package adds).
- `irt_items` is the only IRT table without RLS — the bank is a global
  resource, not user-scoped. Documented in module README.
- `aggregate_scores` integration is **additive** — `interview_scores`
  shape unchanged; new `irt_thetas` key is a list of `{dimension, theta,
  standard_error, n_items, converged}` dicts.

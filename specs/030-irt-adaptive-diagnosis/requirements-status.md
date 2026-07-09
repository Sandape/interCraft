# REQ-030 Requirements Status

**Feature**: IRT-Based Adaptive Ability Diagnosis
**Cycle**: v2 — REQ-030 (US1 partial)
**Date**: 2026-06-25

US1 shipped (item bank + 2-PL IRT + θ estimation). US2 / US3 / US4 + 3-PL +
retest-reliability production measurement are explicitly deferred — see
`tasks.md` "Phase 5+ Deferrals" section.

## Functional Requirements

| FR | Description | US | Status | Evidence |
|---|---|---|---|---|
| FR-001 | Each interview question tagged with IRT item (a, b, c) | US1 | partial | `Item` model has `difficulty_b` + `discrimination_a` (2-PL). `model` column supports `3pl` (US2+). 50 seed items inserted via `seed.py`. |
| FR-002 | IRT parameters calibrated from response data (MML) | US1/US3 | partial | `engine.estimate_theta_mle` does Newton-Raphson MLE on log-likelihood. **Item-level calibration (MML across many users) is US3** — US1 ships hardcoded seed parameters. |
| FR-003 | Calibration as batch job (offline ARQ) | US3 | ⏳ deferred | US3 scope. |
| FR-004 | Items with <30 responses marked "uncalibrated" | US1 | partial | `status` column has CHECK constraint + Literal in `ItemStatus`. US1 defaults all seeds to `uncalibrated`. Promotion logic in US3. |
| FR-005 | Items with extreme parameters flagged | US3 | ⏳ deferred | `status='flagged'` enum exists in CHECK constraint; logic in US3. |
| FR-006 | Model configurable per dimension (2-PL / 3-PL) | US1 | partial | `model` column on `irt_items` is `TEXT` with CHECK `IN ('2pl','3pl')`. US1 only uses `2pl`. 3-PL estimator in US2+. |
| FR-007 | System estimates θ per dimension after each interview | US1 | done | `aggregate_scores_node` emits `irt_thetas` (additive) when ≥3 IRT responses exist per dimension. `_compute_irt_thetas` calls `estimate_theta_mle` per dimension. |
| FR-008 | Ability profile displays θ + SE + CI | US1/US2 | partial | θ + SE stored in `irt_ability_thetas`. **Frontend display + confidence interval computation** ⏳ deferred to a follow-up cycle. |
| FR-009 | θ estimates persisted with timestamps | US1 | done | `irt_ability_thetas.created_at` populated by DB `func.now()`. Latest-row query pattern supported by `list_for_user`. |
| FR-010 | Retest reliability ≥0.85 measurable | US3 | ⏳ deferred | Requires production data; out of scope for US1 (hardcoded seed items only). |
| FR-011 | Interview graph supports "diagnostic mode" | US2/US4 | ⏳ deferred | Adaptive question picker (US2) + interview graph opt-in branch (US4). |
| FR-012 | Adaptive selection within ±0.5 logits of running θ | US2 | ⏳ deferred | Information-gain-maximizing selector in US2. |
| FR-013 | Fallback to uncalibrated items with prior estimates | US2 | ⏳ deferred | Adaptive selector's last-resort path. |
| FR-014 | New items enter bank with prior estimate + refine as responses accumulate | US3 | ⏳ deferred | Calibration + drift logic in US3. |
| FR-015 | Item retirement without deleting response history | US1 | done | `irt_item_responses.item_id` is `ON DELETE SET NULL` — retirement preserves the row. Verified in migration `0020_irt_item_bank.py`. |
| FR-016 | Bank health dashboard endpoint | US3 | ⏳ deferred | US3. |
| FR-017 | Drift detection across calibration runs | US3 | ⏳ deferred | US3. |
| FR-018 | Mock LLM client can produce responses with known difficulty | n/a | n/a | IRT math doesn't depend on LLM. US1 ships 50 seed items with hardcoded (a, b). |
| FR-019 | Eval suite verifies θ stability under prompt changes | US3+ | ⏳ deferred | 026 eval suite integration in US3+. |

## Success Criteria

| SC | Description | Status | Notes |
|---|---|---|---|
| SC-001 | Each dimension has ≥10 calibrated items with response_count ≥30 | partial | **Quantity**: 10 items per dimension (50 total) — ✓. **Calibration status**: all uncalibrated in US1 (US3 promotes them). |
| SC-002 | Retest reliability ≥0.85 | ⏳ deferred | Production measurement; requires US3 calibration + production data. |
| SC-003 | θ SE ≤ 0.5 for users with ≥3 interviews | partial | `engine.estimate_theta_mle` returns finite SE. With 5–10 responses (one interview), SE is typically 0.5–0.8. Improvement requires more items or higher `a`. SC achievable in US3+ with calibrated bank. |
| SC-004 | Adaptive mode selects within ±0.5 logits of θ for ≥70% of selections | ⏳ deferred | US2. |
| SC-005 | Calibration batch ≤30 minutes | ⏳ deferred | US3. |
| SC-006 | New items reach "calibrated" within 50 responses | ⏳ deferred | US3. |
| SC-007 | Items with extreme parameters flagged within 1 calibration run | ⏳ deferred | US3. |
| SC-008 | Retest reliability improves from ~0.5 baseline to ≥0.85 | ⏳ deferred | SC-002 dependent. |

## US1 Acceptance Scenarios

Per spec `spec.md` §US1:

1. **Historical responses → calibration batch with b, a, c + convergence status** — ⏳ US3 (US1 only ships the math + storage)
2. **Item with <30 responses → "uncalibrated" + prior estimate + excluded from θ** — ✓ partial. `status='uncalibrated'` enum exists; US3 implements the threshold logic. US1's `aggregate_scores` sidecar **does** skip uncalibrated items (filters by `status='calibrated'` via `list_calibrated`). Seed items are uncalibrated in US1.
3. **Converged calibration → maintainer view of (a, b, response_count, SE, last-calibrated)** — ⏳ US3 (UI is post-US3).
4. **Discrimination below threshold → flagged for review** — ⏳ US3 (CHECK constraint + enum in place).

## Coverage Summary

| Area | US1 (shipped) | US2 | US3 | US4 |
|---|---|---|---|---|
| Math (2-PL) | ✓ | (3-PL?) | | |
| Math (3-PL) | | ⏳ | | |
| Item bank storage | ✓ | | | |
| Item responses storage | ✓ | | | |
| Ability thetas storage | ✓ | | | |
| Seed items | ✓ | | | |
| Calibration batch (ARQ) | | | ⏳ | |
| Adaptive question selection | | ⏳ | | |
| Interview graph "diagnostic mode" | | | | ⏳ |
| Drift detection | | | ⏳ | |
| Bank health dashboard | | | ⏳ | |
| Retest reliability production measurement | | | ⏳ | |
| Frontend θ display | ⏳ (post-US1) | | | |

## Test Evidence

- 26 unit tests in `tests/unit/test_irt_engine.py` (math)
- 16 unit tests in `tests/unit/test_irt_schemas.py` (Pydantic)
- 4 integration tests in `tests/integration/test_ability_diagnose_irt.py` (sidecar)
- **46 new tests**, 0 regressions vs. baseline 591
- **637 passed, 26 skipped** (full backend suite)

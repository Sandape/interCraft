# Implementation Plan: REQ-030 IRT-Based Adaptive Ability Diagnosis

**Branch**: `[030-irt-adaptive-diagnosis]` | **Date**: 2026-06-25 | **Spec**: [./spec.md](./spec.md)

## Summary

Replace the fixed 5-question + weighted-average ability diagnosis with a
psychometrically sound IRT-based pipeline. The system estimates per-dimension
ability θ (theta) on a logit scale using a 2-parameter logistic (2-PL)
Item Response Theory model, with a self-contained item bank, Newton-Raphson
MLE for θ, and a non-replacing integration alongside the existing
`ability_diagnose` graph.

This plan covers **US1 (item bank + calibrated IRT parameters + θ estimation
math)** as the foundation. US2 (adaptive question selection), US3 (item bank
maintenance / calibration batch / drift detection), US4 (adaptive mode
opt-in to interview), 3-PL (guessing parameter), and retest-reliability
production measurement are explicitly deferred.

## Technical Context

- **Language/Version**: Python 3.11 (project baseline; matches `pyproject.toml`).
- **Primary Dependencies**: SQLAlchemy 2.0 async, Alembic, structlog, Pydantic v2.
  **No new package dependencies** for US1 — pure-Python Newton-Raphson avoids
  needing numpy / scipy. The prompt mentioned `scipy.optimize` as a fallback;
  we ship the ~50-line closed-form Newton-Raphson instead to keep the
  install footprint zero (L004 api-quota-risk adjacent — avoid dependency
  churn in v2 cycle).
- **Storage**: PostgreSQL with RLS (mirrors `agent_memory` pattern from 028).
  Three new tables: `irt_items`, `irt_item_responses`, `irt_ability_thetas`.
  No DB-level cascading changes to existing ability_dimensions — θ lives in
  a parallel table, consumed by `aggregate_scores` opt-in path.
- **Testing**: pytest (asyncio_mode=auto, existing pattern). Unit tests for
  2-PL probability, θ estimation, item bank loader, plus an integration test
  for `aggregate_scores` with 5 mock responses producing θ + SE.
- **Target Platform**: Linux server (production), Windows 11 + bash (dev).
  No platform-specific code.
- **Project Type**: backend library + small CLI + DB migration.
- **Performance Goals**:
  - θ estimation: O(n) log-likelihood evaluation per Newton step, ≤10 steps
    to convergence. With 5–30 responses per user, <1ms per call.
  - Item bank loader: one read per dimension, indexed by status.
- **Constraints**:
  - Pure Python (no numpy/scipy).
  - No LLM call inside IRT math (math is deterministic).
  - Self-contained library (Constitution I): zero FastAPI/DB dependency in
    the math layer — `irt.engine` and `irt.schemas` are pure-Python.
  - RLS-enabled, user-scoped tables (mirrors `agent_memory` 028).

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Library-First | ✅ Pass | `app/modules/irt/` self-contained. Math + schemas pure-Python; `repository.py` is the only DB-coupled surface. README documents API + 2-PL vs 3-PL rationale. |
| II. CLI Interface | ✅ Pass | `python -m scripts.irt_estimate_theta --user-id <uuid> --dimension <key>` prints θ + SE to stdout; errors to stderr. No flags = prints usage + exits 2. |
| III. Test-First | ✅ Pass | 2-PL probability and Newton-Raphson θ estimation unit tests written **before** implementation. Ground-truth fixtures: known (a=1, b=0) + balanced responses → θ̂ ≈ 0 (error < 0.3 logit). |
| IV. Integration Tests | ✅ Pass | `test_ability_diagnose_irt_integration` runs `aggregate_scores` with 5 mock responses + seeded item bank, asserts θ + SE present in output. |
| V. Observability | ✅ Pass | structlog events: `irt.theta_estimated` (user_id, dimension, theta, se, n_items, converged), `irt.engine.convergence_failed` (theta, hessian, attempts). No PII in log attrs. |
| VI. Versioning | ✅ Pass | IRT library has no public API surface beyond math + repository; schema migration is forward-only. Item status enum (`calibrated` / `uncalibrated` / `retired`) is in CHECK constraint. |
| VII. Documentation | ✅ Pass | `app/modules/irt/README.md` describes 2-PL vs 3-PL, math formulation, θ estimation algorithm, item bank lifecycle, and example CLI invocation. |

## Project Structure

### Documentation (this feature)

```text
specs/030-irt-adaptive-diagnosis/
├── plan.md              # This file
├── tasks.md             # Phase 2 tasks (US1 only implemented, rest ⏳)
├── spec.md              # Source of truth
├── data-model.md        # Item / ItemResponse / AbilityTheta / CalibrationRun
└── contracts/
    └── irt-api.md       # Public math API (function signatures, return shapes)
```

### Source Code

```text
backend/app/modules/irt/
├── README.md            # Constitution VII — usage, math, lifecycle
├── __init__.py          # Re-exports: Item, ItemResponse, AbilityTheta, IRTEngine, schemas
├── engine.py            # 2-PL P(θ), log-likelihood, gradient/hessian, Newton-Raphson
├── models.py            # Item / ItemResponse / AbilityTheta / CalibrationRun ORM
├── repository.py        # ItemRepository / ItemResponseRepository / AbilityThetaRepository
├── schemas.py           # Pydantic: ItemCreate, ItemOut, ItemResponseIn, ThetaEstimate
├── seed.py              # seed_items_for_dimension() — hardcoded 10 items per dim
├── cli.py               # typer CLI: estimate_theta / list_items / seed_items
└── tests/               # Internal unit tests (engine math)
    ├── __init__.py
    └── test_engine.py

backend/app/agents/nodes/ability_diagnose/
├── aggregate_scores.py  # UPDATED: detect irt_items; if available, compute θ via engine
│                        # and emit `irt_theta` + `irt_se` alongside `interview_scores`
│                        # (does not replace; emits parallel data)
└── (other nodes unchanged)

backend/migrations/versions/
└── 0020_irt_item_bank.py  # irt_items, irt_item_responses, irt_ability_thetas + RLS

backend/scripts/
└── irt_estimate_theta.py   # Entry point: python -m scripts.irt_estimate_theta ...

backend/tests/
├── unit/
│   ├── test_irt_engine.py            # 2-PL probability + Newton-Raphson ground truth
│   ├── test_irt_repository.py        # repository CRUD + RLS smoke (no DB needed)
│   ├── test_irt_schemas.py           # Pydantic validation
│   └── test_irt_seed.py              # seed loader produces ≥10 items per dimension
└── integration/
    └── test_ability_diagnose_irt.py  # aggregate_scores emits θ + SE from 5 mock responses
```

**Structure Decision**: Single new self-contained module at
`backend/app/modules/irt/`, mirroring the `agent_memory` 028 pattern. One
small additive change to `aggregate_scores.py` so the existing graph gains
IRT output without breaking the current weighted-average path. All IRT math
lives in `engine.py` (no DB / FastAPI imports) to keep the math layer
unit-testable in pure CPython without infrastructure.

## 2-PL Model — Math Specification

The 2-parameter logistic (2-PL) IRT model for a binary response `u ∈ {0, 1}`:

```
P(u=1 | θ; a, b) = 1 / (1 + exp(-a(θ - b)))
                  = σ(a(θ - b))           # σ = logistic sigmoid
```

**Parameters**:
- `a` ∈ (0, ∞) — discrimination (slope at b). Higher a → steeper ICC, more
  informative item.
- `b` ∈ (-∞, ∞) — difficulty (ability level at which P = 0.5).
- `c` (3-PL only) — pseudo-guessing lower asymptote. **Not used in US1.**

**Item Response Function (IRF)**:
```
P_i(θ) = σ(a_i (θ - b_i))
```

### θ Estimation — Marginal MLE via Newton-Raphson

Given observed responses `u = (u_1, ..., u_n)` and known item parameters
`{(a_i, b_i)}`, the log-likelihood of θ is:

```
ℓ(θ; u, a, b) = Σ_i [ u_i log P_i(θ) + (1 - u_i) log(1 - P_i(θ)) ]
```

**Closed-form gradient** (per-item derivative, summed):
```
dℓ/dθ = Σ_i a_i (u_i - P_i(θ))
```

**Closed-form Hessian** (second derivative):
```
d²ℓ/dθ² = -Σ_i a_i² P_i(θ) (1 - P_i(θ))
```

**Newton-Raphson update** (single-parameter case):
```
θ_{k+1} = θ_k - (dℓ/dθ) / (d²ℓ/dθ²)
       = θ_k + Σ_i a_i (u_i - P_i(θ_k)) / Σ_i a_i² P_i(θ_k)(1 - P_i(θ_k))
```

**Convergence**: |θ_{k+1} - θ_k| < 0.01 logits OR max 25 iterations.

**Standard error** (observed information):
```
SE(θ̂) = 1 / sqrt(-H(θ̂))  = 1 / sqrt(Σ_i a_i² P_i(θ̂)(1 - P_i(θ̂)))
```

**Edge handling**:
- All-correct or all-incorrect: log(0) guarded by clamp `max(ε, min(1-ε, P))`
  with ε = 1e-9.
- Zero-information items (a = 0): skipped in gradient/hessian sum.
- Convergence failure: log `irt.engine.convergence_failed`, return θ at
  last iteration with SE flagged via `converged: False` in result.

## Data Model

### `irt_items`

| Column | Type | Notes |
|---|---|---|
| id | UUID v7 | PK |
| dimension | TEXT | e.g. `tech_depth`, `architecture` (matches existing DIMENSIONS list) |
| question_text_hash | TEXT | SHA-256 of question text (for dedup; no full text in DB) |
| difficulty_b | NUMERIC(6,3) | logit scale, typically [-3, 3] |
| discrimination_a | NUMERIC(6,3) | logit slope, typically [0.3, 2.5] |
| model | TEXT | `2pl` (US1) or `3pl` (US2+) |
| status | TEXT | `uncalibrated` / `calibrated` / `retired` / `flagged` |
| response_count | INT | Counter, maintained by repository on insert |
| standard_error | NUMERIC(6,3) | SE at calibration; 0 for uncalibrated |
| last_calibrated_at | TIMESTAMPTZ | NULL for uncalibrated |
| created_at / updated_at | TIMESTAMPTZ | |

Constraints:
- CHECK `status IN ('uncalibrated','calibrated','retired','flagged')`
- CHECK `model IN ('2pl','3pl')`
- CHECK `difficulty_b BETWEEN -6 AND 6`
- CHECK `discrimination_a >= 0`
- CHECK `response_count >= 0`
- Partial unique index on `(dimension, question_text_hash) WHERE status != 'retired'`
- RLS: **disabled** (item bank is global, not user-scoped). Per spec, items
  belong to the bank, not the user. This deviates from `agent_memory` 028 RLS
  pattern intentionally — documented in module README.

### `irt_item_responses`

| Column | Type | Notes |
|---|---|---|
| id | UUID v7 | PK |
| user_id | UUID | FK → users.id, RLS-scoped |
| item_id | UUID | FK → irt_items.id, ON DELETE SET NULL (preserve response history even if item retired) |
| response | TEXT | `correct` / `incorrect` (US1 binary only) |
| score | NUMERIC(4,2) | Raw LLM score 0–10 (preserved for future 3-PL partial-credit analysis) |
| source_interview_id | UUID | FK → interview_sessions.id, nullable |
| created_at | TIMESTAMPTZ | |

Constraints:
- CHECK `response IN ('correct','incorrect')`
- CHECK `score BETWEEN 0 AND 10`
- RLS: **enabled** (`user_id` scope).

### `irt_ability_thetas`

| Column | Type | Notes |
|---|---|---|
| id | UUID v7 | PK |
| user_id | UUID | FK → users.id, RLS-scoped |
| dimension | TEXT | |
| theta | NUMERIC(6,3) | Estimated θ on logit scale |
| standard_error | NUMERIC(6,3) | SE at estimation |
| n_items | INT | Number of items used in estimation |
| source_interview_id | UUID | The interview that produced this θ |
| model | TEXT | `2pl` (US1) |
| converged | BOOLEAN | False if Newton-Raphson hit max iterations |
| created_at | TIMESTAMPTZ | |

Constraints:
- CHECK `theta BETWEEN -6 AND 6`
- CHECK `standard_error > 0`
- CHECK `n_items >= 1`
- RLS: **enabled** (`user_id` scope).

## API Contracts

See `contracts/irt-api.md` for full signatures. Public surface:

```python
# Pure math (no DB, no FastAPI)
from app.modules.irt.engine import (
    probability_2pl,        # P(θ; a, b) → float
    estimate_theta_mle,     # (responses: list[Response], items: list[ItemParams]) → ThetaResult
)

# Schemas
from app.modules.irt.schemas import ThetaResult, ItemOut, ItemResponseIn

# Repository (DB-coupled, used by graph + scripts)
from app.modules.irt.repository import ItemRepository, AbilityThetaRepository
```

## Scope Decision — Why US1 Only

The full 4-US implementation requires:

- US3: ARQ calibration batch over historical responses (0502A consideration:
  L001 checkpointer pattern in ability_diagnose shows ARQ entrypoints need
  retry wrappers; touching ARQ for IRT risks the same fragility).
- US2: ability_diagnose graph refactor to support adaptive mode (touches
  LangGraph, interrupts, WS — high surface area).
- US4: interview graph changes for opt-in adaptive mode (parallel to US2).
- US2/3/4: real calibrated parameters need production response data;
  US1 ships with hardcoded seed items, sufficient to validate the math
  pipeline.

US1 delivers the load-bearing math (Newton-Raphson θ estimation) and the
storage layer (3 tables + repository). US2/3/4 plug into the math without
modifying it.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected |
|---|---|---|
| IRT module in `backend/app/modules/irt/` (new top-level module) | US1 establishes the foundation; US2/3/4 need a stable library surface | Putting IRT under `ability_diagnose` couples it to the agent graph; US2/3/4 need library access from CLI, scripts, and (potentially) interview graph. |
| No RLS on `irt_items` | Item bank is global (not user-scoped) | Per-user items would fragment calibration; spec FR-001 implies a shared bank. |
| `irt_item_responses.item_id` ON DELETE SET NULL | Spec FR-015: "retirement must not delete historical response data" | ON DELETE CASCADE would lose calibration history. |

## Migration Plan

`0020_irt_item_bank.py` (depends on `0019_027_resume_avatar`):

- Creates `irt_items` (no RLS), `irt_item_responses` (RLS), `irt_ability_thetas` (RLS).
- Indexes: `idx_irt_items_dimension_status`, `idx_irt_responses_user_dim`, `idx_irt_thetas_user_dim`.
- Downgrade drops all three tables.
- Forward-only; not enforced in production until 030 US1 ships.

## Open Questions / Decisions Deferred

1. **3-PL guessing parameter**: Deferred. Open-ended interview questions
   don't have a meaningful `c`; 2-PL is sufficient for US1.
2. **Calibration source of truth**: US1 ships seed items with hardcoded
   parameters. US3 will replace with parameters calibrated from historical
   interview responses.
3. **Replace weighted average vs. parallel emit**: US1 emits IRT data
   alongside weighted scores; downstream consumers can opt in. A switch to
   "θ replaces weighted average" is gated on SC-002 (retest reliability
   ≥0.85) being met with production data — US3.
4. **Multiple-choice items**: Future items may use 3-PL. US1 stores `model`
   column to allow mixed 2-PL/3-PL in the same bank; only 2-PL is exercised
   by the current θ estimator.

# irt — Item Response Theory library for ability diagnosis (REQ-030 US1)

Self-contained module implementing the **2-parameter logistic (2-PL) Item
Response Theory** model and **Newton-Raphson marginal MLE** for per-dimension
user ability θ (theta) estimation.

## US1 Scope

| Capability | Status |
|---|---|
| 2-PL probability `P(θ; a, b)` | Shipped |
| θ estimation via Newton-Raphson MLE | Shipped (pure-Python, ~50 lines) |
| Item bank (50 seed items, 5 dimensions × 10) | Shipped (hardcoded `a`, `b`) |
| Item responses + thetas storage | Shipped (3 tables + RLS) |
| `aggregate_scores_node` sidecar | Shipped (additive — does not replace weighted scores) |
| CLI for seed/list/estimate | Shipped |
| **3-PL guessing parameter `c`** | ⏳ US2+ |
| **Offline calibration batch (ARQ)** | ⏳ US3 |
| **Adaptive question selection (info-gain)** | ⏳ US2 |
| **Adaptive interview mode opt-in** | ⏳ US4 |
| **Retest reliability ≥0.85 production validation** | ⏳ gated on US3 + production data |

## Why 2-PL (not 3-PL) in US1?

3-PL adds a `c` (pseudo-guessing) parameter, mostly meaningful for
multiple-choice items. The current interview pipeline produces **open-ended
responses** evaluated by an LLM — there is no random-guessing lower asymptote
on a 0-10 graded answer. Adding `c` would either fit to noise (overfitting
on small response counts) or require MC item types that don't exist yet.

US1 ships 2-PL. The `model` column on `irt_items` and `irt_ability_thetas`
is a `TEXT` with CHECK `IN ('2pl','3pl')` so a future US2/3 release can
introduce 3-PL items without a schema migration.

## Architecture

```
interview graph (after completion)
    │
    └── ARQ task diagnose_after_interview
            │
            └── ability_diagnose graph
                    │
                    └── aggregate_scores_node
                            │
                            ├── interview_scores  (existing weighted avg)
                            │
                            └── irt_thetas  ← NEW (additive sidecar)
                                    │
                                    ├── ItemResponseRepository.list_for_user
                                    │     (RLS-scoped by app.user_id GUC)
                                    │
                                    ├── group responses by item dimension
                                    ├── look up (a, b) for each item
                                    │
                                    └── estimate_theta_mle(triples) per dim
                                            │
                                            ├── gradient / hessian closed form
                                            ├── Newton-Raphson θ̂
                                            └── SE = 1/sqrt(-H(θ̂))
```

## Math — 2-PL Probability

```
P(correct | θ; a, b) = σ(a(θ - b))   where σ(x) = 1 / (1 + exp(-x))
```

| Parameter | Range | Meaning |
|---|---|---|
| `a` (discrimination) | [0, 5] | Slope of the ICC at `b`. Higher a → sharper cutoff. |
| `b` (difficulty) | [-6, +6] | Ability level at which P = 0.5. |
| `θ` (ability) | [-6, +6] | User's latent trait. Mean 0, SD 1 in the population. |

## θ Estimation — Newton-Raphson MLE

For observed responses `u = (u_1, …, u_n)` with known `(a_i, b_i)`:

```
ℓ(θ)   = Σ_i [u_i log P_i + (1 - u_i) log (1 - P_i)]    # log-likelihood
dℓ/dθ  = Σ_i a_i (u_i - P_i)                            # gradient (closed form)
d²ℓ/dθ² = -Σ_i a_i² P_i(1 - P_i)                        # Hessian (closed form)
θ_{k+1} = θ_k - (dℓ/dθ) / (d²ℓ/dθ²)                     # Newton step
SE(θ̂)  = 1 / sqrt(-d²ℓ/dθ²|_{θ̂})                       # observed information
```

**Convergence**: `|θ_{k+1} - θ_k| < 0.01` logit OR 25 iterations max.
**Edge handling**: P is clamped to `[ε, 1-ε]` (ε=1e-9) before `log` to
keep ℓ finite for all-correct / all-incorrect patterns. Items with `a ≈ 0`
are skipped in the gradient/Hessian sums (no information).
**Bounds**: θ is clamped to `[-6, +6]` each iteration.

The implementation is **pure Python** (no `numpy` / `scipy` dependency) —
~50 lines of math. See `engine.py` for the closed-form derivations.

## Tables

### `irt_items` (global, no RLS)

| Column | Type | Notes |
|---|---|---|
| id | UUID v7 | PK |
| dimension | TEXT | `tech_depth` / `architecture` / `engineering_practice` / `communication` / `algorithm` |
| question_text_hash | TEXT | SHA-256 of question text |
| difficulty_b | NUMERIC(6,3) | logit scale [-6, +6] |
| discrimination_a | NUMERIC(6,3) | logit slope [0, 5] |
| model | TEXT | `2pl` (US1) / `3pl` (US2+) |
| status | TEXT | `uncalibrated` (US1 default) / `calibrated` / `retired` / `flagged` |
| response_count | INT | Bumped on response insert (US3) |
| standard_error | NUMERIC(6,3) | 0 for uncalibrated |
| last_calibrated_at | TIMESTAMPTZ | NULL for uncalibrated |
| created_at / updated_at | TIMESTAMPTZ | |

Constraints: `status IN (...)`, `model IN ('2pl','3pl')`, `difficulty_b
BETWEEN -6 AND 6`, `discrimination_a >= 0 AND <= 5`, partial unique index
`(dimension, question_text_hash) WHERE status != 'retired'`.

**Why no RLS?** The item bank is a global psychometric resource. Calibration
requires aggregating responses from many users onto each item; per-user item
tables would fragment the data. Per-user RLS is enforced on the responses +
thetas tables (those carry private per-user information).

### `irt_item_responses` (RLS user-scoped)

| Column | Type | Notes |
|---|---|---|
| id | UUID v7 | PK |
| user_id | UUID | FK → users.id, RLS-scoped |
| item_id | UUID | FK → irt_items.id, **ON DELETE SET NULL** (preserves history on item retirement, FR-015) |
| response | TEXT | `correct` / `incorrect` (US1 binary) |
| score | NUMERIC(4,2) | Raw LLM score 0-10 (preserved for 3-PL future) |
| source_interview_id | UUID | nullable |
| created_at | TIMESTAMPTZ | |

### `irt_ability_thetas` (RLS user-scoped)

| Column | Type | Notes |
|---|---|---|
| id | UUID v7 | PK |
| user_id | UUID | FK → users.id, RLS-scoped |
| dimension | TEXT | |
| theta | NUMERIC(6,3) | Estimated θ (logit scale [-6, +6]) |
| standard_error | NUMERIC(6,3) | > 0 |
| n_items | INT | ≥ 1 |
| source_interview_id | UUID | nullable |
| model | TEXT | `2pl` (US1) |
| converged | BOOLEAN | False if Newton-Raphson hit max iterations |
| created_at | TIMESTAMPTZ | |

## Public API

### Math (no DB / FastAPI dependency)

```python
from app.modules.irt.engine import (
    probability_2pl,        # P(θ; a, b) → float
    log_likelihood,         # ℓ(θ; responses) → float
    gradient,               # dℓ/dθ → float
    hessian,                # d²ℓ/dθ² → float
    estimate_theta_mle,     # (responses) → ThetaResult
    ThetaResult,            # dataclass(theta, se, n_items, converged, iterations)
)
```

### Schemas (Pydantic, validation boundary)

```python
from app.modules.irt.schemas import (
    ItemCreate,             # validation: a ∈ [0, 5], b ∈ [-6, +6], status Literal
    ItemOut,                # public shape
    ItemResponseIn,         # response: 'correct'/'incorrect', score: 0-10
    ThetaEstimate,          # aggregate_scores output shape
    ThetaResultSchema,      # engine output wrapper
)
```

### Repository (DB-coupled, async)

```python
from app.modules.irt.repository import (
    ItemRepository,
    ItemResponseRepository,
    AbilityThetaRepository,
)

# Item bank (global, no RLS)
repo = ItemRepository(session)
await repo.upsert_seed_items(seed_items)        # idempotent
items = await repo.list_for_dimension("tech_depth")
items = await repo.list_calibrated("tech_depth")  # US1: empty (all uncalibrated)

# Responses (caller must set app.user_id GUC for RLS)
rr = ItemResponseRepository(session)
await rr.insert_response(user_id=..., item_id=..., response="correct", score=8.5)
responses = await rr.list_for_user(user_id, dimension="tech_depth", since=...)

# θ history (caller must set app.user_id GUC)
tr = AbilityThetaRepository(session)
await tr.insert(user_id=..., dimension=..., theta=1.5, standard_error=0.4, n_items=10)
rows = await tr.list_for_user(user_id, dimension="tech_depth", limit=20)
```

## CLI (Constitution II)

```bash
# Seed 50 hardcoded items (5 dims × 10) into the bank
uv run intercraft irt seed-items

# Re-seed (drop existing items first)
uv run intercraft irt seed-items --reset

# List items in one dimension
uv run intercraft irt list-items --dimension tech_depth
uv run intercraft irt list-items --dimension tech_depth --status uncalibrated
uv run intercraft irt list-items --dimension tech_depth --json

# Estimate θ for a user on one dimension (or all)
uv run intercraft irt estimate-theta --user-id <uuid> --dimension tech_depth
uv run intercraft irt estimate-theta --user-id <uuid>
# stdout: dimension=tech_depth theta=1.234 se=0.567 n_items=10 converged=true
```

Errors to stderr. JSON output for list operations. Exit code 0 even when no
dimensions have enough data (silent skip — caller decides what "no data"
means).

## Integration with `ability_diagnose` Graph

The `aggregate_scores_node` was extended to emit an `irt_thetas` key
additively. The existing `interview_scores` shape is **unchanged** (backward
compatible with the rest of the graph). The graph caller can read either or
both.

```python
# Per-dimension θ from the latest interview
result = await graph.run(user_id=user_id, session_id=session_id)
interview_scores = result["interview_scores"]   # weighted average (unchanged)
irt_thetas = result.get("irt_thetas", [])       # IRT (new, empty if no data)
```

A minimum of 3 IRT responses per dimension is required (below that, SE is
effectively infinite and the result is not actionable). Failures in the IRT
sidecar are caught and logged — they never break the existing graph path.

## Observability (Constitution V)

| Event | When | Fields |
|---|---|---|
| `irt.engine.theta_estimated` | After `estimate_theta_mle` converges | `theta`, `se`, `n_items`, `iterations` |
| `irt.engine.convergence_failed` | Newton-Raphson hit max iterations | `theta`, `iterations` |
| `irt.aggregate_scores.failed` | IRT sidecar raises (DB / math error) | `user_id`, `session_id`, `error` |
| `irt.items.seed` | After seed insert | `attempted`, `inserted` |

No PII in log fields. All events go through structlog.

## Item Bank Lifecycle (US1 → US3)

```
                  seed (US1)
                      │
                      ▼
              ┌──────────────┐
              │ uncalibrated │  ← initial state for all seed items
              └──────┬───────┘
                     │   US3: offline calibration batch
                     │   (≥30 responses per item + MML convergence)
                     ▼
              ┌──────────────┐
              │  calibrated  │  ← selectable for θ estimation
              └──────┬───────┘
                     │
            ┌────────┴────────┐
            │                 │
            ▼                 ▼
      ┌──────────┐      ┌──────────┐
      │ retired  │      │ flagged  │
      └──────────┘      └──────────┘
      (compromised)     (extreme a / drift)
      (excluded from    (review queue)
       selection;
       history kept)
```

US1 only exercises the **uncalibrated** state (seed insert + read).
`calibrated` / `retired` / `flagged` are reserved for US3.

## Testing

- `app/modules/irt/tests/` (internal) — math + repo smoke
- `tests/unit/test_irt_engine.py` — 26 tests: 2-PL probability boundaries
  (P(b)=0.5, monotonicity, symmetry, numerical stability), Newton-Raphson
  convergence, all-correct / all-incorrect edge cases, ground-truth recovery
  (simulated responses from known θ, |error| < 0.3 logit), SE monotonicity
  with sample size, seed loader
- `tests/unit/test_irt_schemas.py` — 16 tests: Pydantic validation
  boundaries (a/b range, NaN, status enum, score range)
- `tests/integration/test_ability_diagnose_irt.py` — 4 tests: sidecar
  end-to-end with 5 mock responses producing θ + SE, no-data path,
  <3-responses-skip path, pure-math ground truth

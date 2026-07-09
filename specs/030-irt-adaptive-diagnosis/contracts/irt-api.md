# REQ-030 IRT Public API Contract

**Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md) | **Status**: US1 done, US2/3/4 ⏳ deferred.

This is the **public surface** of the `app.modules.irt` library. Anything
NOT listed here is internal and may change without notice.

## Math API (no DB / FastAPI dependency)

```python
from app.modules.irt.engine import (
    probability_2pl,        # (theta, a, b) -> float in [0, 1]
    log_likelihood,         # (theta, responses) -> float
    gradient,               # (theta, responses) -> float  [dℓ/dθ]
    hessian,                # (theta, responses) -> float  [d²ℓ/dθ²]
    estimate_theta_mle,     # (responses) -> ThetaResult
    ThetaResult,            # dataclass
)
```

### `probability_2pl(theta: float, a: float, b: float) -> float`

```
P(correct | θ; a, b) = σ(a(θ - b))   σ = logistic sigmoid
```

Numerically stable (no overflow at extreme θ). Always in [0, 1].

### `estimate_theta_mle(responses, *, max_iter=25, tol=0.01) -> ThetaResult`

```python
@dataclass(frozen=True)
class ThetaResult:
    theta: float            # Estimated θ in [-6, +6]
    standard_error: float   # 1 / sqrt(-H(θ̂)); +inf if no information
    n_items: int            # Number of (a, b, u) triples provided
    converged: bool         # True if |θ_{k+1} - θ_k| < tol
    iterations: int         # Newton steps executed (<= max_iter)
```

- `responses`: `list[tuple[float, float, int]]` of `(a, b, u)` where `u ∈ {0, 1}`.
- Empty input → `theta=0.0, se=inf, n_items=0, converged=True, iterations=0`.
- Convergence failure → `converged=False`, returns last-iteration θ.

## Schemas (Pydantic, validation boundary)

```python
from app.modules.irt.schemas import (
    ItemCreate,             # a ∈ [0, 5], b ∈ [-6, +6], status Literal
    ItemOut,                # public ORM shape
    ItemResponseIn,         # response: 'correct'/'incorrect', score: 0-10
    ThetaEstimate,          # aggregate_scores output shape
    ThetaResultSchema,      # engine output wrapper
)
```

### `ItemCreate`

| Field | Type | Constraint |
|---|---|---|
| `dimension` | str | 1-64 chars |
| `question_text_hash` | str | 1-128 chars |
| `difficulty_b` | float | -6 ≤ b ≤ 6 |
| `discrimination_a` | float | 0 ≤ a ≤ 5 |
| `model` | Literal['2pl', '3pl'] | default `'2pl'` |
| `status` | Literal['uncalibrated', 'calibrated', 'retired', 'flagged'] | default `'uncalibrated'` |

`extra='forbid'` — unknown fields raise `ValidationError`.

### `ThetaEstimate` (aggregate_scores sidecar output)

| Field | Type | Constraint |
|---|---|---|
| `dimension` | str | 1-64 chars |
| `theta` | float | -6 ≤ θ ≤ 6 |
| `standard_error` | float | > 0 |
| `n_items` | int | >= 0 |
| `converged` | bool | required |

## Repository API (DB-coupled, async)

```python
from app.modules.irt.repository import (
    ItemRepository,            # global, no RLS
    ItemResponseRepository,    # caller must set app.user_id GUC
    AbilityThetaRepository,    # caller must set app.user_id GUC
)
```

### `ItemRepository`

```python
async def upsert_seed_items(items: Sequence[ItemCreate]) -> int
    # Idempotent. Returns number of newly-inserted rows.

async def get_by_id(item_id: UUID) -> Item | None

async def list_for_dimension(
    dimension: str, *, status: str | None = None
) -> list[Item]
    # Order by difficulty_b ASC.

async def list_calibrated(dimension: str, *, limit: int = 100) -> list[Item]
    # US1: returns []. US3: returns calibrated subset.
```

### `ItemResponseRepository`

```python
async def insert_response(
    *, user_id: UUID, item_id: UUID, response: str, score: float,
    source_interview_id: UUID | None = None,
) -> ItemResponse
    # Caller must set app.user_id GUC (RLS).

async def list_for_user(
    user_id: UUID, *, dimension: str | None = None,
    since: datetime | None = None, limit: int = 200,
) -> list[ItemResponse]
    # Newest first. Joins to irt_items to filter by dimension.
```

### `AbilityThetaRepository`

```python
async def insert(
    *, user_id: UUID, dimension: str, theta: float, standard_error: float,
    n_items: int, source_interview_id: UUID | None = None,
    model: str = "2pl", converged: bool = True,
) -> AbilityTheta
    # Caller must set app.user_id GUC (RLS).

async def list_for_user(
    user_id: UUID, *, dimension: str | None = None, limit: int = 50,
) -> list[AbilityTheta]
    # Newest first.
```

## `aggregate_scores_node` Integration

`app/agents/nodes/ability_diagnose/aggregate_scores.py` is updated
**additively** to emit `irt_thetas` alongside `interview_scores`. The
existing `interview_scores` shape is unchanged (backward compatible).

```python
result = await aggregate_scores_node({
    "user_id": "...",
    "session_id": "...",
})

result["interview_scores"]   # list[dict]   — UNCHANGED (weighted avg)
result["irt_thetas"]         # list[dict]   — NEW (additive, may be [])
```

Each `irt_thetas` entry:
```python
{
    "dimension": str,           # e.g. "tech_depth"
    "theta": float,             # in [-6, +6]
    "standard_error": float,    # > 0
    "n_items": int,             # >= 3 (below threshold → skipped)
    "converged": bool,          # Newton-Raphson success
}
```

**Sidecar semantics**:
- The IRT sidecar is best-effort. Any exception in θ computation is
  logged (`irt.aggregate_scores.failed`) and `irt_thetas=[]` is emitted
  — the existing graph path is never broken.
- A dimension is included in `irt_thetas` only if the user has ≥3 IRT
  responses to items in that dimension.

## CLI (Constitution II)

```bash
# Seed 50 hardcoded items into the bank
uv run intercraft irt seed-items [--reset]

# List items in one dimension
uv run intercraft irt list-items --dimension <key> [--status <s>] [--json]

# Estimate θ for a user
uv run intercraft irt estimate-theta --user-id <uuid> [--dimension <key>]
```

Output: one `key=value` line per dimension to stdout. Errors to stderr.
Exit code 0 when at least one dimension produced an estimate; otherwise
0 with `# no dimensions produced estimates` on stderr.

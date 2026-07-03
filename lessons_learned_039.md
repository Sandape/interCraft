# Lessons learned — REQ-039 B1 (2026-07-03)

## FastAPI sub-dep signature pitfall

**Problem**: A `require_capability(...)` factory returned an inner async
function with `user_id: UUID` parameter — no `Depends(...)` annotation.
FastAPI treats unannotated `UUID` parameters as **required query
params**, so any endpoint calling `Depends(require_capability(...))`
returned 422 with `"field": "query.user_id"`.

**Fix**: Inner dep must accept user_id via dependency chain, not as a
query param:

```python
async def _dep(
    user_id: Annotated[UUID, Depends(get_caller_user_id_dep())],
) -> bool:
    ...
```

**Lesson**: All inner deps that consume a request-scoped value
(auth user_id, db session, settings, etc.) MUST annotate the param
with `Annotated[T, Depends(...)]`. Bare annotations = query param
parsing.

## Alembic chain with parallel teams

**Problem**: Worktree branch predates the full migration chain (0012-
0016, 0022-0026 belong to other concurrent teams). `alembic upgrade
head` failed with `KeyError: '0016_interview_plan'` even when my own
migration's `down_revision` was correct.

**Fix v1 (REJECTED)**: Make my migration a **branch root** —
`down_revision = None` + `branch_labels = ("039_log_center",)`. This
FAILED on review because alembic's `ScriptDirectory` walks **every**
file in the versions/ directory to build the `revision_map` BEFORE
applying `branch_labels` semantics. So if any other file references a
non-existent parent, the loader crashes with `KeyError` regardless of
how my own migration is declared. Tester's `Base.metadata.create_all`
bootstrap masked this because it never invoked alembic at all.

**Fix v2 (ACCEPTED)**: Insert 5 no-op stub bridge migrations (0012-
0016) in my own commit so the chain is **complete** end-to-end. The
0016 stub reuses the `revision` ID `"0016_interview_plan"` (so 0017
finds it as a parent) but declares `down_revision = "0015_039_bridge"`.
The 4 other stubs (0012-0015) declare a new unique revision ID and
chain through 0011. My real migration (0022) reattaches to
`0021_a2a_messages`. All stubs have `branch_labels = None` — alembic
refuses two revisions sharing the same `branch_label`.

**Lesson**: `branch_labels` is a **graph declaration** tool, not a
**loader bypass**. If the upstream chain is broken, alembic's
ScriptDirectory will reject the entire load before branch resolution
runs. The only safe fix is to fill the gap with stub bridges. On
merge to master, the stubs MUST be deleted in the same commit (or
master's real 0012-0016 will collide with the stubs' revision IDs).

**Anti-pattern to avoid**: declaring `down_revision = None` +
`branch_labels = "..."` and self-reporting "fixed" without running
`alembic upgrade head` or `alembic history`. Both commands load the
full script directory and will surface broken upstream chains. Trust
command output, not branch-label semantics (see
`feedback_dev_report_truthfulness.md`).

## asyncpg :bind::jsonb parse error

**Problem**: `text("... :payload::jsonb ...")` with a bind param
caused `syntax error at or near ":"` because asyncpg's parameterized
SQL doesn't allow cast operators directly after `:bind`.

**Fix**: Use `bindparam("payload", type_=JSONB)` to let SQLAlchemy
emit the cast:

```python
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import bindparam

stmt = text("INSERT ... VALUES (:payload)").bindparams(
    bindparam("payload", type_=JSONB)
)
await conn.execute(stmt, {"payload": {"messages": [...]}})
```

**Lesson**: For JSONB/JSONB[] params in asyncpg, always use typed
`bindparam` rather than inline `:bind::jsonb` cast syntax.

## Capability dep cycle import

**Problem**: `require_capability(capability)` factory needs to call
`get_caller_user_id` (defined in api.py), but auth.py is imported
first by api.py → circular import.

**Fix**: Lazy import via a module-level cache + getter function:

```python
_caller_user_id_dep = None

def get_caller_user_id_dep():
    global _caller_user_id_dep
    if _caller_user_id_dep is None:
        from app.modules.admin_console.api import get_caller_user_id
        _caller_user_id_dep = get_caller_user_id
    return _caller_user_id_dep
```

**Lesson**: For dependency factories that wrap each other, defer the
import until first call. Module-level `_dep_holder` caches the
resolution so subsequent calls stay free.
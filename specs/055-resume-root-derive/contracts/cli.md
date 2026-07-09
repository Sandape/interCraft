# CLI Contract: resume-derive

**Module**: `backend/app/modules/resume_derive/cli.py`  
**Invocation** (planned): `cd backend && uv run python -m app.modules.resume_derive.cli …`  
**Also**: register under existing agent/module CLI aggregator if present.

## Commands

### `run`

Start a derive synchronously in-process (dev/CI) or enqueue ARQ (`--async`).

```text
resume-derive run --user-id <uuid> --job-id <uuid> --pages <1|2|3> [--template <id>] [--async]
```

**Stdout (`--json`)**: `{ "run_id", "status", "derived_resume_id?" }`  
**Exit**: `0` success or needs_guidance recorded; `2` validation (NO_JD/NO_ROOT); `1` hard failure.

### `status`

```text
resume-derive status --run-id <uuid> [--json]
```

### `validate-pages`

Count pages of a PDF file or re-render HTML fixture.

```text
resume-derive validate-pages --pdf <path> --expect <1|2|3>
resume-derive validate-pages --html <path> --expect <1|2|3>   # optional HTML estimate mode
```

**Exit**: `0` match; `3` mismatch; print `{ "actual", "expected" }`.

### `parse-jd` (optional helper)

```text
resume-derive parse-jd --job-id <uuid> [--json]
```

For debugging JD structured parse without full derive.

## I/O protocol

- Human-readable default; `--json` for machine consumption (Constitution II).
- Secrets never printed; user ids allowed in structured logs.

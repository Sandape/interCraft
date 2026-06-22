# Quickstart: Error Coach 3-Correct E2E

**Branch**: `021-error-coach-e2e` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

Runnable validation guide. Run these commands to prove the feature works
end-to-end.

---

## Prerequisites

- Node 20+, Python 3.11+, `uv` installed
- Local Redis on `6379` (per `project_local_env` memory)
- Online Postgres reachable (per `backend/.env` `DATABASE_URL`)
- `backend/.env` with `DEEPSEEK_API_KEY` (unused in mock mode, but file must exist)
- Frontend deps installed (`npm install` once)
- Backend deps installed (`cd backend && uv sync` once)
- Backend migrations applied (`cd backend && uv run alembic upgrade head`)

---

## 1. Run the new E2E spec only

The E2E spec uses Playwright's `APIRequestContext` only (no browser UI), so
the frontend dev server is not required. The backend must be started with
mock-LLM env vars so `get_llm_client()` returns `MockLLMClient`.

```bash
# Terminal 1 — start backend with mock LLM
cd backend
LLM_MOCK_MODE=1 \
LLM_MOCK_SCENARIO_PATH="D:/Project/eGGG/tests/e2e/round-2/fixtures/error-coach-scenarios/active.json" \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — run the spec (serial, because tests share a single scenario file)
npm run e2e -- tests/e2e/round-2/error-coach-3-correct.spec.ts --project=chromium --workers=1
```

Expected: 3 tests pass (HAPPY-01, EDGE-01, ABORT-01), ≤ 60s total.

> `playwright.config.ts` does **not** auto-manage the backend webServer —
> E2E runs against externally-started dev servers. The `--workers=1` flag is
> required because the scenario file is a shared fixed path; parallel tests
> would race on it.

---

## 2. Run the full round-2 suite (regression guard)

```bash
npm run e2e -- tests/e2e/round-2/ --project=chromium
```

Expected: ≥ 21 tests pass (18 existing + 3 new), 0 fail, 0 skip.

---

## 3. Run backend mock-client unit test

```bash
cd backend
uv run pytest tests/test_llm_client_mock.py -v
```

Expected: tests pass, verifying:
- `LLM_MOCK_MODE` unset → `get_llm_client()` returns real `LLMClient`
- `LLM_MOCK_MODE=1` → returns `MockLLMClient`
- `MockLLMClient` reads scenario JSON correctly
- `MockLLMClient` falls back to defaults on missing scenario

---

## 4. Verify 004 SC-002 flip

```bash
grep "SC-002" specs/004-phase5-agent-subgraphs/requirements-status.md
```

Expected: `| SC-002 | ... | done | ... | tests/e2e/round-2/error-coach-3-correct.spec.ts |`

```bash
grep "004" specs/README.md | head -5
```

Expected: 004 row Notes no longer mentions "SC-002 requires a live-LLM scoring loop".

---

## 5. Verify backend diff scope

```bash
git diff master -- backend/app/agents/nodes/error_coach/
git diff master -- backend/app/api/v1/agents_error_coach.py
git diff master -- backend/app/services/error_coach_service.py
```

Expected: all three commands produce **empty output** (no business logic changes).

```bash
git diff master -- backend/app/agents/graphs/error_coach.py
```

Expected: ~25 lines changed. Two latent bugs fixed (documented in plan.md
Complexity Tracking):
1. `builder.compile(interrupt_after=["hint_ladder"])` — graph now pauses after
   each hint, waiting for user input. Without this, `start()` ran all 3
   rounds with itself and `submit_answer` was a no-op.
2. `abort()` uses `as_node="evaluate"` to skip a pending evaluate, and calls
   `decrement_frequency` so abandoned sessions decrement frequency.

```bash
git diff master -- backend/app/agents/llm_client.py
```

Expected: ~25 lines added, all within `get_llm_client()` factory function,
gated by `LLM_MOCK_MODE` env var. Includes mtime-based cache so the score
sequence in `MockLLMClient` persists across invokes within a session.

---

## 6. Manual real-LLM verification (optional, out of CI scope)

```bash
# Without mock mode
npm run e2e -- tests/e2e/round-2/error-coach-3-correct.spec.ts --project=chromium
```

Expected: tests may pass or fail depending on DeepSeek's scoring consistency.
This mode is for manual verification only; CI runs with `LLM_MOCK_MODE=1`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `thread_id` returns but messages 500 | checkpointer connection dropped | restart backend, retry (Phase 4 known issue, to be fixed in 023) |
| `frequency` unchanged after 3 correct | `decrement_frequency` not called | verify `correct_count >= 3` in response, check backend logs for `error_question_not_found` |
| Mock LLM returns real DeepSeek response | `LLM_MOCK_MODE` not set | check `playwright.config.ts` webServer env, or set env var manually |
| E2E flakes on 10th run | checkpointer idle timeout | restart backend between runs, or increase connection pool keepalive |

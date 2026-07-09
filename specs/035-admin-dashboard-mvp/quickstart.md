# REQ-035 Quickstart Validation

This guide describes validation scenarios for the Strong Debug MVP. Commands are
expected after implementation tasks are generated and completed.

## Prerequisites

- Backend dependencies installed with `uv`.
- Frontend dependencies installed with `npm install`.
- Database migrated:

```bash
cd backend
uv run alembic upgrade head
```

- Admin console local dev path is `http://localhost:5173/admin-console` through
  `npm run dev` or `npm run dev:admin`.
- Backend API running at `http://localhost:8000`.

## Current Implementation Slice

The current REQ-035 pass implements the admin entry point, protected admin shell,
deterministic dashboard read model, deterministic Strong Debug demo seed
fixture/summary, policy-level payload visibility, shared masked-raw validation,
safe cURL generation, coverage CLI/API, privacy audit CLI, retention dry-run
CLI, and minimal trace/node/LLM endpoints.

Known limitations for this slice:

- Database migrations, ORM models, and repository primitives now exist, but the
  admin/observability API services still use deterministic read models until
  repository wiring and integration tests land.
- Full dashboard aggregation still uses deterministic REQ-035 read-model data
  rather than persisted PM metric snapshots.
- REQ-035 integration and Playwright tests are not present yet.
- Full frontend `typecheck` and default `vite build` are blocked by unrelated
  existing `src/modules/resume/v2` and `src/pages/PublicResumeV2` errors; the
  isolated admin-only Vite build passes.

## 1. Seed Strong Debug Demo Data

```bash
cd backend
uv run python -m app.modules.agent_observability.cli seed-strong-debug-demo \
  --env local \
  --json
```

Expected:

- One PM/admin user with dashboard access.
- One developer/reviewer user with trace and masked raw access.
- One successful trace.
- One failed trace linked to agent node, LLM call, eval failure, and badcase.
- One expired masked raw payload for retention validation.

## 2. Start Services

Backend:

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

User-facing frontend and the hidden admin path share the same Vite server:

```bash
npm run dev
```

The admin convenience script opens the dedicated admin path:

```bash
npm run dev:admin
```

Expected:

- User-facing app and admin console have different local entry paths on the
  same dev host.
- Admin console loads its own shell and does not depend on the user-facing route
  `/pm-dashboard`.
- Ordinary product pages do not expose an admin navigation entry.

## 3. Validate Admin Access Boundary

Run backend contract/integration tests:

```bash
cd backend
uv run pytest tests/contract/test_035_admin_console_contract.py -q
uv run pytest tests/integration/test_035_admin_access.py -q
```

Expected:

- Unauthenticated users get 401 before any dashboard or trace data.
- Authenticated non-admin users get 403.
- PM dashboard capability can view dashboard but cannot reveal masked raw.
- Developer/reviewer capability can reveal masked raw only after reason entry.

## 4. Validate Product Dashboard Freshness

```bash
cd backend
uv run pytest tests/integration/test_035_dashboard_freshness.py -q
```

Expected:

- Dashboard sections show last refresh time.
- New source data appears within 15 minutes or affected sections are marked
  stale.
- Complete, partial, empty, stale, and error states are distinguishable.

## 5. Validate Trace Drilldown

```bash
cd backend
uv run pytest tests/contract/test_035_trace_explorer_contract.py -q
uv run pytest tests/integration/test_035_trace_capture_chain.py -q
```

Expected:

- Search by user/business/trace/agent/node/model/status returns matching trace.
- Trace detail shows parent-child hierarchy.
- Agent run detail shows node timeline.
- Node detail shows input/output/state diff in redacted or masked form.
- LLM call detail shows provider, endpoint, model, params, usage, latency,
  retries, provider request id, and linked payloads.
- Eval failure links back to trace, node, LLM call, badcase, prompt version,
  rubric version, and model.

## 6. Validate Masked Raw Reveal And cURL Redaction

```bash
cd backend
uv run pytest tests/unit/test_035_curl_redaction.py -q
uv run pytest tests/unit/test_035_payload_visibility.py -q
uv run pytest tests/integration/test_035_masked_raw_access.py -q
```

Expected:

- Default production-mode views expose no raw business text.
- Masked raw reveal requires `MASKED_RAW_VIEW` and a reason.
- Every reveal creates an audit event with actor, reason, target, visibility
  mode, and timestamp.
- PM-only, owner-only without debug role, non-admin, and unauthenticated users
  cannot reveal masked raw.
- Reconstructed cURL contains method, endpoint, model, body shape, and trace
  context, but never real API keys, bearer tokens, cookies, refresh tokens, or
  private credentials.

## 7. Validate Eval Center

```bash
cd backend
uv run pytest tests/contract/test_035_eval_center_contract.py -q
```

Expected:

- Eval run list shows passing and failing runs.
- Eval case detail shows score dimensions.
- At least one failing case links to trace, LLM call, and badcase.
- Latest gate status is visible.

## 8. Validate Retention

```bash
cd backend
uv run python -m app.modules.agent_observability.cli retention-purge \
  --env production \
  --dry-run \
  --json

cd backend
uv run pytest tests/integration/test_035_retention.py -q
```

Expected:

- PM metric snapshots are retained for 180 days.
- Redacted traces/spans are retained for 60 days.
- Masked raw payloads are retained for 14 days.
- Expired masked raw payloads are inaccessible.

## 9. Validate Coverage Gaps

```bash
cd backend
uv run python -m app.modules.agent_observability.cli coverage-report \
  --env local \
  --out docs/evidence/035-admin-dashboard-mvp/coverage-report.json \
  --json
```

Expected:

- All centralized Agent/LLM flows are listed as covered.
- Legacy or direct-provider bypass paths are listed as coverage gaps.
- High-severity unaccepted gaps cause non-zero exit per contract.

## 10. Validate End-To-End Admin UI

```bash
npm run test -- src/admin
npm run typecheck
npm run e2e -- tests/e2e/035-admin-dashboard-mvp.spec.ts
```

Expected:

- Admin shell loads at `/admin-console` on the frontend dev server.
- PM can answer usage, funnel drop-off, resume suggestion adoption, interview
  completion, and AI cost/failure trend from the dashboard.
- Developer/reviewer can find seeded failed run, inspect node I/O, inspect LLM
  call, generate redacted cURL, and open linked eval case.
- Unauthorized users never see dashboard, trace, payload, eval, or snapshot
  data.

## Evidence

Store validation outputs under:

```text
docs/evidence/035-admin-dashboard-mvp/
|-- coverage-report.json
|-- privacy-audit.json
|-- dashboard-snapshot.md
|-- e2e-admin-dashboard.png
`-- test-summary.md
```

Update `specs/035-admin-dashboard-mvp/requirements-status.md` only after code
and verification evidence are both present.

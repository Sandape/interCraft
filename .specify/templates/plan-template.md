# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [runtime versions or NEEDS CLARIFICATION]

**Resolved Dependencies**: [exact versions from lockfile/runtime, lockfile path or snapshot hash]

**Dependency Support**: [support evidence/status for every production dependency; unsupported or
unverified dependency deviation with concrete migration target; `N/A` only with rationale]

**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]

**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]

**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]

**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

**Risk Classification**: [highest feature R0/R1/R2/R3 with rationale; distinguish from story priority and service tier]

**Operation Risk Matrix**: [classify each governed operation/effect; highest applicable class wins]

**Execution Model**: [request/response, durable dispatch intent + ARQ job, LangGraph thread, scheduled task, or N/A]

**AI/Agent State**: [typed state, checkpointer/store, thread/execution identity, effect fencing,
live-version/retention matrix, decoder/upcasters, N-1 rolling compatibility, or N/A with rationale]

**External Dependencies**: [model/tool/search providers, timeout/retry/idempotency policy, or N/A]

**Observability & Privacy**: [correlation IDs, required audit facts, redaction/retention policy]

**Migration & Rollout**: [database-enforced migration exclusion/ledger, resumable backfill,
separate expand/contract releases, checkpoint/payload compatibility, backout/roll-forward]

**Operational Release Unit**: [service/capability boundary and inherited vs. capability-specific controls]

## Constitution Check

*SCREEN before Phase 0; re-check after Phase 1 design. Pre-screen research is allowed only
for `RESEARCH REQUIRED`; `BLOCKED` stops work. Post-design `FAIL` stops implementation.*

| Gate | Applicability / inherited control | Pre-screen (`CLEAR` / `RESEARCH REQUIRED` / `BLOCKED`) | Post-design (`PASS` / `N/A WITH RATIONALE` / `APPROVED DEVIATION` / `FAIL`) | Evidence link |
|---|---|---|---|---|
| Boundaries & composition roots | [scope/owner] | [status] | [status] | [router/service/domain/adapter and API/worker/CLI/graph wiring] |
| Typed contracts & authorization | [scope/owner] | [status] | [status] | [Pydantic/OpenAPI/errors, object authorization, execution-time revalidation] |
| Async, transactions & process isolation | [scope/owner] | [status] | [status] | [lifespans, session-per-task, external I/O boundary, multi-worker state] |
| Durable dispatch & concurrency ownership | [scope/owner] | [status] | [status] | [task+intent transaction, dispatcher/reconciler, admission, authoritative-write/effect fencing] |
| LangGraph state & compatibility | [scope/owner or N/A rationale] | [status] | [status] | [state/reducers/checkpointer, interrupt/resume, live-version matrix/upcasters, N-1 rolling tests] |
| Agent safety & data lifecycle | [operation risk/owner or N/A rationale] | [status] | [status] | [immutable authorization receipt, tool/effect intent, injection controls, per-store lifecycle/deletion propagation] |
| Test-first & evaluation | [risk-based scope/owner] | [status] | [status] | [RED/equivalent evidence, unit/contract/integration/E2E/fault/eval] |
| Observability, release & dependency support | [release unit/inheritance/owner] | [status] | [status] | [audit/telemetry, SLO/runbook/capacity/rollback, support status] |

Every `APPROVED DEVIATION` requires a complete Deviation Register entry. Non-waivable
controls from the constitution must be `PASS`, otherwise implementation is blocked.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: InterCraft web application
backend/
├── app/
│   ├── modules/           # domain/application/API boundaries
│   ├── agents/            # LangGraph state, nodes, graphs, adapters
│   ├── api/               # cross-module API composition
│   └── workers/           # ARQ durable background execution
└── tests/

src/
├── components/
├── pages/
├── api/
└── repositories/

tests/e2e/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Deviation Register

> **Fill only for post-design `APPROVED DEVIATION`. An expired deviation is `FAIL`.**

| Control / Clause | Scope | Risk | Supplier Support Evidence / Status | Concrete Migration Target | Why Needed | Simpler Alternative Rejected | Compensating Controls | Owner | Approver | Expiry | Removal Task |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [control] | [bounded scope] | [concrete risk] | [required for dependency deviation; otherwise N/A with rationale] | [required for dependency deviation; otherwise N/A with rationale] | [reason] | [why insufficient] | [measurable controls] | [role/name] | [role/name] | [YYYY-MM-DD] | [task/link] |

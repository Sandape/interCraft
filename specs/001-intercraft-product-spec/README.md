# 001 Product Baseline

Status: `done / in_progress`

This directory is the product baseline source. It contains the original product
spec plus phase-specific plans for the core platform.

## Current Status

| Phase | Status | Canonical Documents | Notes |
|---|---|---|---|
| Phase 1 - P0 baseline | done | [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [quickstart.md](./quickstart.md) | Auth, sessions, resumes, blocks, versions, and frontend foundation. |
| Phase 2 - P1 entities | in_progress | [phase-2.md](./phase-2.md), [research-phase-2.md](./research-phase-2.md), [data-model-phase-2.md](./data-model-phase-2.md), [quickstart-phase-2.md](./quickstart-phase-2.md) | Error questions, abilities, tasks, activities, jobs, interview sessions. |
| Phase 3 - sync and offline | done | [phase-3.md](./phase-3.md), [research-phase-3.md](./research-phase-3.md), [data-model-phase-3.md](./data-model-phase-3.md), [quickstart-phase-3.md](./quickstart-phase-3.md) | Locks and outbox. |

## Contracts

Use [contracts/README.md](./contracts/README.md) as the API contract index for
Phase 1 through Phase 3.

## Agent Notes

- Treat this directory as baseline context, not the active feature unless the
  task explicitly targets Phase 1, Phase 2, or Phase 3 behavior.
- Load only the phase documents relevant to the current task.
- Later feature specs can extend this baseline, but they should not silently
  rewrite it.


# Legacy Requirements Map

This map explains how historical requirement documents relate to canonical
SpecKit specs. Use historical documents for background only; implementation
should start from `specs/README.md`.

## Root Historical Documents

| Legacy Document | Status | Canonical Replacement |
|---|---|---|
| [PERSISTENCE_REQUIREMENTS.md](../PERSISTENCE_REQUIREMENTS.md) | legacy | [specs/001-intercraft-product-spec](../../specs/001-intercraft-product-spec/) plus later feature specs. |
| [DEVELOPMENT_ROADMAP.md](../DEVELOPMENT_ROADMAP.md) | legacy | [specs/README.md](../../specs/README.md) and feature `tasks.md`. |
| [ANALYSIS_REPORT.md](../ANALYSIS_REPORT.md) | historical source | Use as audit/rationale context only. Promote unresolved items into `backlog.md` before implementation. |
| Phase release and closure reports | evidence/report | Keep as historical delivery records; do not use as current requirements. |

## Module Documents

| Module | Legacy Document | Canonical Specs |
|---|---|---|
| M01 Infrastructure | [01-infrastructure.md](../modules/01-infrastructure.md) | [001](../../specs/001-intercraft-product-spec/) |
| M02 Database and ORM | [02-database-orm.md](../modules/02-database-orm.md) | [001](../../specs/001-intercraft-product-spec/) |
| M03 Cache, queue, crypto | [03-cache-queue-crypto.md](../modules/03-cache-queue-crypto.md) | [001](../../specs/001-intercraft-product-spec/), [003](../../specs/003-phase4-interview-agent/) |
| M04 Account and auth | [04-account-auth.md](../modules/04-account-auth.md) | [001](../../specs/001-intercraft-product-spec/) |
| M05 Sessions, devices, RLS | [05-session-device-rls.md](../modules/05-session-device-rls.md) | [001](../../specs/001-intercraft-product-spec/) |
| M06 Resume branches and blocks | [06-resume-branch-block.md](../modules/06-resume-branch-block.md) | [001](../../specs/001-intercraft-product-spec/), [002](../../specs/002-resume-editor-enhancement/), [017](../../specs/017-topbar-new-resume/), [019](../../specs/019-cross-module-linking/) |
| M07 Resume versioning | [07-resume-versioning.md](../modules/07-resume-versioning.md) | [001](../../specs/001-intercraft-product-spec/), [002](../../specs/002-resume-editor-enhancement/) |
| M08 Error Book | [08-error-book.md](../modules/08-error-book.md) | [001](../../specs/001-intercraft-product-spec/), [016](../../specs/016-error-book-completion/), [019](../../specs/019-cross-module-linking/) |
| M09 Ability Profile | [09-ability-profile.md](../modules/09-ability-profile.md) | [006](../../specs/006-personal-ability-profile/) |
| M10 Tasks and activities | [10-task-activity.md](../modules/10-task-activity.md) | [001](../../specs/001-intercraft-product-spec/) |
| M11 Interview history | [11-interview-history.md](../modules/11-interview-history.md) | [001](../../specs/001-intercraft-product-spec/), [003](../../specs/003-phase4-interview-agent/) |
| M12 Locks and WS control | [12-pessimistic-lock-ws-control.md](../modules/12-pessimistic-lock-ws-control.md) | [001 Phase 3](../../specs/001-intercraft-product-spec/phase-3.md) |
| M13 Client offline sync | [13-client-offline-sync.md](../modules/13-client-offline-sync.md) | [001 Phase 3](../../specs/001-intercraft-product-spec/phase-3.md) |
| M14 LangGraph foundation | [14-langgraph-foundation.md](../modules/14-langgraph-foundation.md) | [003](../../specs/003-phase4-interview-agent/), [004](../../specs/004-phase5-agent-subgraphs/) |
| M15 Interview Agent | [15-interview-agent.md](../modules/15-interview-agent.md) | [003](../../specs/003-phase4-interview-agent/), [019](../../specs/019-cross-module-linking/) |
| M16 Resume Optimize Agent | [16-resume-optimize-agent.md](../modules/16-resume-optimize-agent.md) | [004](../../specs/004-phase5-agent-subgraphs/), [018](../../specs/018-fix-product-defects/) |
| M17 Error Coach Agent | [17-error-coach-agent.md](../modules/17-error-coach-agent.md) | [004](../../specs/004-phase5-agent-subgraphs/), [016](../../specs/016-error-book-completion/), [018](../../specs/018-fix-product-defects/) |
| M18 Ability Diagnose Agent | [18-ability-diagnose-agent.md](../modules/18-ability-diagnose-agent.md) | [004](../../specs/004-phase5-agent-subgraphs/), [006](../../specs/006-personal-ability-profile/) |
| M19 General Coach Agent | [19-general-coach-agent.md](../modules/19-general-coach-agent.md) | [004](../../specs/004-phase5-agent-subgraphs/), [018](../../specs/018-fix-product-defects/) |
| M20 Lifecycle and retention | [20-lifecycle-deletion-retention.md](../modules/20-lifecycle-deletion-retention.md) | [005](../../specs/005-phase6-global-capabilities/) |
| M21 Import and export | [21-import-export.md](../modules/21-import-export.md) | [005](../../specs/005-phase6-global-capabilities/), [012](../../specs/012-resume-export-gateway/) |
| M22 Audit and observability | [22-audit-observability-reconciliation.md](../modules/22-audit-observability-reconciliation.md) | [005](../../specs/005-phase6-global-capabilities/) |
| M23 Frontend migration | [23-frontend-migration.md](../modules/23-frontend-migration.md) | [001](../../specs/001-intercraft-product-spec/), [source map](../architecture/source-map.md) |


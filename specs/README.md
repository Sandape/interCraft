# InterCraft Specs Index

This directory is the canonical requirements source for InterCraft. Keep the
feature directories in place so SpecKit and `.specify/feature.json` continue to
resolve stable paths.

## How To Use

1. Read this index first.
2. Read the active feature README, then its `spec.md`, `contracts/`, and
   `tasks.md` as needed.
3. Treat `docs/modules/*` and the old roadmap documents as historical context,
   not implementation authority.
4. When implementation status changes, update both the feature-level row here
   and the requirement-level status table in the feature directory.

## Status Vocabulary

| Status | Meaning |
|---|---|
| `active` | Current SpecKit feature or current implementation focus. |
| `in_progress` | Accepted requirement with partial implementation or pending validation. |
| `planned` | Accepted or drafted requirement not yet started. |
| `done` | Implemented and backed by tests or verification evidence. |
| `blocked` | Accepted requirement waiting on an external dependency or unresolved decision. |
| `deferred` | Explicitly postponed to a future feature. |
| `superseded` | Replaced by a newer spec. |
| `legacy` | Historical source material only. |

## Active

| ID | Feature | Status | Source Of Truth | Requirement Status | Notes |
|---|---|---|---|---|---|
| 019 | Cross-Module Linking | active | [spec.md](./019-cross-module-linking/spec.md) | [requirements-status.md](./019-cross-module-linking/requirements-status.md) | Current `.specify/feature.json` target. Implementation evidence exists in the worktree and still needs final verification. |

## In Progress

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 003 | Phase 4 Interview Agent | in_progress | [spec.md](./003-phase4-interview-agent/spec.md) | Interview WS, LLM, and reporting workstream. |
| 006 | Personal Ability Profile | in_progress | [spec.md](./006-personal-ability-profile/spec.md) | Ability profile, sharing, export, and admin contracts. |
| 010 | Topbar Utility Actions | in_progress | [spec.md](./010-topbar-utility-actions/spec.md) | Topbar utility UI. |
| 012 | Resume Export Gateway | in_progress | [spec.md](./012-resume-export-gateway/spec.md) | Resume export API and UI gateway. |
| 013 | User Avatar | in_progress | [spec.md](./013-user-avatar/spec.md) | Avatar upload and storage. |
| 015 | Jobs Status Alignment | in_progress | [spec.md](./015-jobs-status-alignment/spec.md) | Jobs transition alignment. |
| 016 | Error Book Completion | in_progress | [spec.md](./016-error-book-completion/spec.md) | Error book API and UI completion. |
| 017 | Topbar New Resume Branch | in_progress | [spec.md](./017-topbar-new-resume/spec.md) | Topbar resume creation flow. |
| 018 | Fix Product Defects | in_progress | [spec.md](./018-fix-product-defects/spec.md) | Product quality batch with multiple contracts. |

## Planned

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 002 | Resume Editor Enhancement | planned | [spec.md](./002-resume-editor-enhancement/spec.md) | Editor and PDF service enhancement. |
| 004 | Phase 5 Agent Subgraphs | planned | [spec.md](./004-phase5-agent-subgraphs/spec.md) | Agent subgraph extension. Update this row if implementation resumes. |
| 005 | Phase 6 Global Capabilities | planned | [spec.md](./005-phase6-global-capabilities/spec.md) | Account, audit, subscription, and content capabilities. |

## Done Or Baseline

| ID | Feature | Status | Source Of Truth | Notes |
|---|---|---|---|---|
| 001 | Product Baseline | done / in_progress | [README.md](./001-intercraft-product-spec/README.md) | Phase 1 and Phase 3 are done; Phase 2 remains in progress. |
| 007 | Interview Resume Guardrails | done | [spec.md](./007-interview-resume-guardrails/spec.md) | Guardrail behavior is treated as delivered unless reopened. |
| 008 | Interview Delete Feedback | done | [spec.md](./008-interview-delete-feedback/spec.md) | Delivered feature; verify before changing. |
| 009 | Interview Search Recovery | done | [spec.md](./009-interview-search-recovery/spec.md) | Delivered feature; verify before changing. |
| 011 | Global Search | done | [spec.md](./011-global-search/spec.md) | Delivered search capability; verify before changing. |
| 014 | Job Tracking | done | [spec.md](./014-job-tracking/spec.md) | Job tracking baseline used by later features. |

## Blocked

No blocked specs are recorded in this index. If a requirement is blocked, add it
here and explain the dependency in that feature's requirement status table.

## Legacy / Superseded

| Source | Status | Replacement |
|---|---|---|
| [docs/modules/](../docs/modules/) | legacy | See [docs/requirements/legacy-map.md](../docs/requirements/legacy-map.md). |
| [docs/PERSISTENCE_REQUIREMENTS.md](../docs/PERSISTENCE_REQUIREMENTS.md) | legacy | Specs in this directory. |
| [docs/DEVELOPMENT_ROADMAP.md](../docs/DEVELOPMENT_ROADMAP.md) | legacy | This index plus feature-level `tasks.md`. |
| [docs/ANALYSIS_REPORT.md](../docs/ANALYSIS_REPORT.md) | historical source | Use only for rationale and old audit context. |


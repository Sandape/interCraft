# ADR-001: Documentation Structure For Agent Maintenance

## Status

Accepted

## Date

2026-06-17

## Context

InterCraft had several overlapping documentation sources:

- SpecKit feature directories under `specs/`
- module-level historical requirements under `docs/modules/`
- large root documents such as `PERSISTENCE_REQUIREMENTS.md`,
  `DEVELOPMENT_ROADMAP.md`, and `ANALYSIS_REPORT.md`
- test plans, reports, screenshots, and logs spread across `docs/`, root files,
  `e2e/`, and `tests/e2e/`

This made it hard for AI coding agents to know which document was authoritative.
The immediate goal is to improve maintenance without moving runtime source code
or breaking SpecKit path assumptions.

## Decision

1. Use `specs/` as the canonical requirements source.
2. Use `specs/README.md` as the requirements status index.
3. Use feature-level README and requirement status files for active or important
   features.
4. Fold legacy requirement context into `specs/`, then remove unreferenced
   legacy documents once the canonical indexes are in place.
5. Use `tests/e2e/` as the canonical Playwright E2E root.
6. Keep source paths stable for now; document the real source map instead of
   moving `src/` or `backend/app/`.
7. Store future screenshots and snapshots under `docs/evidence/` or
   feature-specific evidence folders.

## Follow-up Decision: Slim Removed Legacy Documents

On 2026-06-17, after the SpecKit documentation system was established, the
project removed legacy requirement documents, old reports, and unreferenced
evidence artifacts. The retained documentation set is now intentionally small:
`specs/`, this `docs/` routing layer, current testing guidance, current evidence
policy, and active feature evidence.

Current active Round-1 defect material is retained because feature 020 still
uses it as implementation evidence. Other historical material can be recovered
from git history if needed, but it is no longer a repository navigation surface.

## Follow-up Decision: Remove Legacy Root E2E

On 2026-06-17, root `e2e/` was removed after still-useful 018 defect coverage
was migrated into `tests/e2e/018-fix-product-defects/`. Future E2E work should
only use `tests/e2e/`; historical root E2E sources remain available through git
history when needed.

## Alternatives Considered

### Move completed and unfinished specs into separate directories

- Pros: Visual separation.
- Cons: Breaks SpecKit and `.specify/feature.json` stable paths.
- Decision: Rejected. Use status indexes and requirement matrices instead.

### Keep `docs/modules` as a parallel requirements source

- Pros: Preserves the original module taxonomy.
- Cons: Creates two competing sources of truth.
- Decision: Rejected. Keep it as legacy context with a mapping file.

### Move frontend source into `frontend/src`

- Pros: Would match some older generated plans.
- Cons: High-risk source move during a dirty worktree and unnecessary for this
  cleanup.
- Decision: Rejected for this phase. Document `src/` as canonical.

## Consequences

- Agents can load a small, reliable context path: `AGENTS.md` ->
  `specs/README.md` -> feature README -> `spec.md` / `contracts` / `tasks`.
- Requirement completion is visible at both feature and FR/SC level.
- Removed legacy documents no longer compete with current specs.
- The cleanup remains low risk because it avoids business logic and schema
  changes.

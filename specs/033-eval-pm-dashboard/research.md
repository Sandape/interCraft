# Research: REQ-033 Automated Eval & PM Dashboard MVP

**Spec**: [./spec.md](./spec.md) | **Plan**: [./plan.md](./plan.md)

## Decision 1: Keep Local Eval Reports Canonical

**Decision**: Local eval JSON/Markdown artifacts remain the canonical eval
record. LangSmith Cloud receives synced datasets/experiments only when enabled
and must never rewrite local pass/fail verdicts.

**Rationale**: ADR-002 explicitly rejects LangSmith as the only source of truth.
Keeping local artifacts canonical protects CI gates from vendor availability,
permissions, and pricing changes.

**Alternatives considered**:
- LangSmith-only eval record: rejected because CI/debug evidence would require
  external access.
- Local-only eval with no LangSmith sync: rejected because developers lose the
  inspection UX the MVP is meant to add.

## Decision 2: Extend Existing Eval Runner Instead Of Creating A Parallel Runner

**Decision**: Build on `backend/app/eval/runner.py`, `golden_loader.py`, and
`cli.py` from feature 026.

**Rationale**: Feature 026 already owns golden-case loading, stale-case
handling, per-case verdicts, and the Chinese-fidelity checker. A second runner
would fragment baselines and make PR gates ambiguous.

**Alternatives considered**:
- New `langsmith_eval/` subsystem: rejected because it duplicates fixture and
  verdict logic.
- Direct LangSmith pytest-only flow: rejected because local JSON must remain
  canonical and reportable without external access.

## Decision 3: Use Optional LangSmith Reporter Boundary

**Decision**: Introduce an optional reporter boundary that receives completed
eval reports and syncs uploadable golden cases/results to LangSmith.

**Rationale**: Reporter separation keeps the eval verdict path deterministic and
allows LangSmith failures to be recorded as sync failures, not eval failures.

**Alternatives considered**:
- Put LangSmith calls inside the core eval loop: rejected because upload failure
  could corrupt eval semantics.
- Offline export file only: rejected because MVP requires LangSmith experiments.

## Decision 4: PM Dashboard Reads Internal Metrics, Not LangSmith

**Decision**: PM Dashboard V1 uses InterCraft-controlled events, metric
snapshots, AI invocation summaries, badcase records, and eval artifacts as
sources. LangSmith links are supplementary drill-downs.

**Rationale**: PM metrics include product funnel, user behavior, cost estimates,
feedback, badcases, and version fields. LangSmith is not the complete source
for those product facts and must not become the cost ledger.

**Alternatives considered**:
- Build dashboard from LangSmith exports: rejected because product usage,
  quota/cost, and compliance facts would be incomplete and vendor-bound.
- Build only static Markdown reports: rejected because PM Dashboard V1 is an
  explicit MVP requirement.

## Decision 5: Use Metric Snapshots For Dashboard V1

**Decision**: Dashboard V1 should consume metric snapshots or bounded aggregate
queries with explicit freshness, not raw trace scans at page-load time.

**Rationale**: PM pages need predictable internal load behavior and clear
freshness. Snapshot-style contracts also make acceptance tests deterministic.

**Alternatives considered**:
- Query every raw event on each dashboard load: rejected due to slow growth and
  inconsistent freshness.
- Build a separate analytics warehouse in MVP: rejected as over-scoped.

## Decision 6: Environment Policy Is The Privacy Gate

**Decision**: Export behavior is controlled by an environment-specific,
versioned redaction policy:

- local/CI: synthetic or approved golden data may upload.
- staging: masked prompt/output only for synthetic, golden, or approved staging
  test data; otherwise metadata + redacted summaries.
- production: metadata + redacted summaries only.

**Rationale**: The policy matches clarified MVP decisions and gives tests a
single contract to validate before any external export.

**Alternatives considered**:
- One policy for all environments: rejected because local/CI golden data and
  production user data have different risk profiles.
- Trust automated masking for all staging traces: rejected because staging can
  contain sensitive user-like content.

## Decision 7: Production Trace Retention Is 30 Days

**Decision**: Production trace metadata and redacted summaries are retained for
30 days after production export is approved.

**Rationale**: The clarified MVP choice favors a longer debugging and trend
review window while still requiring a fixed deletion/inaccessibility check.

**Alternatives considered**:
- 7 days: lower privacy exposure but weak incident lookback.
- 14 days: middle option, rejected by clarification.

## Decision 8: Badcase Promotion Starts With CLI/Documented Review

**Decision**: First-month badcase-to-golden-case promotion is handled by a
CLI/documented review flow; admin UI is deferred.

**Rationale**: This preserves auditability and reduces MVP scope. It also
aligns with the constitution's CLI-first principle.

**Alternatives considered**:
- Build full admin UI in MVP: rejected as unnecessary for first-month volume.
- No promotion workflow until UI exists: rejected because reviewed production
  learning is part of the MVP boundary.

## Decision 9: Dual Approval For Baseline Refresh And Emergency Override

**Decision**: Both baseline refresh and emergency override require PM business
owner plus technical owner approval, with reason, evidence, timestamp, and
affected gate/baseline recorded.

**Rationale**: These actions change the meaning of quality gates and therefore
need both business risk and engineering risk ownership.

**Alternatives considered**:
- Single badcase owner approval: rejected because release gates are broader than
  badcase triage.
- Any maintainer approval: rejected because it weakens regression governance.

## Decision 10: Interfaces Use Additive Contracts

**Decision**: REST/CLI/event contracts use stable names, explicit unknown values
for missing fields, pagination for lists, and additive optional fields for
future extension.

**Rationale**: Dashboard and eval consumers will depend on observable behavior.
Stable, additive contracts reduce churn across frontend, backend, CI, and
future agent workflows.

**Alternatives considered**:
- Free-form JSON blobs only: rejected because requirements demand measurable
  definitions and join fields.
- Versioned parallel APIs for MVP: rejected because one-version additive
  contracts are simpler.

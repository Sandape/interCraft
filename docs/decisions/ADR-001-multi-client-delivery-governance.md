# ADR-001: Multi-Client Delivery Governance

## Status

Accepted (Phase 5a)

## Date

2026-07-12

## Context

The InterCraft repository has multiple clients that may modify code:
Codex (supervising acceptance), Claude Code, Cursor (interactive), Cursor
Automation (future), and human developers working through IDE or CLI. Prior
to this ADR, there was no standardized gate preventing direct-to-`master`
changes, no unified dispatch protocol, and no canonical workflow document
that all clients reference.

Key observations that drove this decision:

1. **No forced PR gate**: Changes could (and did) go directly into `master`
   without review, CI, or dispatch authorization.
2. **Multiple truth sources**: `AGENTS.md`, client-specific rules, and
   historical documents could each claim different workflows.
3. **No dispatch ownership**: Two clients could independently start work on
   the same Issue, causing merge conflicts or duplicate effort.
4. **CI was unreliable**: Pre-existing red CI meant no quality signal at
   merge time.
5. **GitHub Ruleset existed** (Stage-A, ID 18825748) but workflow-level gate
   scripts were missing.
6. **No Issue intake standard**: Issues lacked required fields (`dispatch_id`,
   `base_sha`, `AC hash`, `allowed_paths`) making automated validation
   impossible.

This ADR captures the architecture decisions for the governance system
that addresses these gaps, implemented across Phases 5–10.

## Decision

### D1: Single Canonical SOP

**Decision**: Create a single `docs/engineering/delivery-sop.md` as the
authoritative normative workflow. All client rules reference this document,
never duplicate it.

**Rationale**: A single source of truth prevents divergence between clients.
When the workflow changes, only one document needs updating. Client adapters
(`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`) remain thin — they describe how
to load the SOP, not what the SOP says.

**Consequences**:
- Positive: Single update point, no drift between client interpretations.
- Positive: Each client can describe "how to load rules" without repeating
  "what the rules are."
- Negative: All clients must be able to read and interpret markdown
  documents consistently.

### D2: Issue as Execution Unit, Spec as Truth

**Decision**: Keep `specs/` as the canonical requirements source (per
[ADR-001-documentation-structure.md](./ADR-001-documentation-structure.md)).
An Issue is a single execution unit derived from a spec. A dispatch
authorizes work on that Issue.

**Rationale**: Separating the spec (what to build) from the issue (when to
build it) allows multiple parallel implementations of different specs while
maintaining a single source of truth for each requirement.

**Consequences**:
- Positive: Specs remain stable; Issues track execution state.
- Positive: Multiple Issues can reference the same spec.
- Negative: Requires discipline to keep spec and Issue in sync.

### D3: SpecKit Pointer and Numbering Stability

**Decision**: Do not move `specs/*` directories, even when a feature is
complete. Do not modify `.specify/feature.json` to point to governance specs
during implementation. Keep stable SpecKit paths.

**Rationale**: SpecKit and `.specify/feature.json` depend on stable directory
paths to resolve the active feature. Moving directories or changing the
global pointer breaks this resolution, causing agent confusion.

**Consequences**:
- Positive: Agents can always find the active feature by reading
  `.specify/feature.json` and resolving its path.
- Positive: Completed specs remain navigable at their original paths.
- Negative: The `specs/` directory accumulates done specs alongside active
  ones. Status indexes (`specs/README.md`) distinguish active from done.

### D4: Dispatch Envelope with Deterministic AC Hashing

**Decision**: Every dispatch includes a `dispatch_id`, `base_sha`, `ac_hash`
(computed from a specific `## Canonical Acceptance Statement` heading),
`allowed_paths`, and `governance_version`. The AC hash MUST be a SHA-256
digest of only the canonical AC text, not the entire Issue body or checkbox
list.

**Rationale**:
- A deterministic hash allows automated gate checks to verify that the
  acceptance criteria haven't drifted.
- Hashing only the canonical heading, not mutable checkboxes or comments,
  means normal Issue updates don't invalidate the dispatch.
- Normalization rules (UTF-8 NFC, CRLF→LF, per-line whitespace stripping)
  ensure the same text always produces the same hash across platforms.

**Consequences**:
- Positive: Gate validation is deterministic and automated.
- Positive: Issue editors can update checkboxes and comments without
  invalidating the dispatch.
- Negative: Issue creators must include a properly formatted
  `## Canonical Acceptance Statement` heading. Without it, the gate
  fails closed (`GATE_AC_MALFORMED`).

### D5: Client Rules as Thin Adapters

**Decision**: Client-specific rules files (`AGENTS.md`, `CLAUDE.md`,
`.cursor/rules/agent-delivery.mdc`) are thin adapters that:

1. Reference the SOP for normative workflow content.
2. Describe client-specific loading mechanics (e.g., "Cursor loads
   `.cursor/rules/` automatically; verify by asking X").
3. Do NOT duplicate SOP content, dispatch protocols, or gate rules.

**Rationale**: If SOP content is duplicated in a client adapter, the adapter
becomes a second source of truth that can drift. Thin adapters eliminate
this risk.

**Consequences**:
- Positive: SOP changes propagate to all clients automatically.
- Negative: Each client adapter needs to explain "read the SOP" in a way
  that the client's users find natural.

### D6: GitHub as Merge Boundary

**Decision**: All merges happen through GitHub PRs with squash merge. No
direct pushes to `master`. No local-only merges. No automation scripts
bypass GitHub's merge API.

**Rationale**: GitHub's PR interface provides audit trail (who approved,
what CI ran, what changed), branch protection (Ruleset enforcement), and
collaboration features (review comments, change requests). Bypassing it
loses all of these.

**Consequences**:
- Positive: Full audit trail for every change to `master`.
- Positive: Ruleset enforces PR requirement, squash-only, and required
  approvers.
- Negative: Emergency fixes still require a PR (though the review step
  can be bypassed by Owner PR-only bypass — see D8).

### D7: One Active Dispatch per Issue

**Decision**: At most one active dispatch per Issue. A new dispatch (with
new `dispatch_id`) supersedes the old one. Expired or superseded dispatches
cannot be reactivated.

**Rationale**: Two clients simultaneously working on the same Issue will
conflict. By enforcing one active dispatch, the system ensures clear
ownership and prevents races. If a handoff is needed, the old dispatch is
superseded and a new one created.

**Consequences**:
- Positive: No ambiguity about who owns an Issue.
- Positive: Handoff creates a clean break — old PRs cannot pass gate.
- Negative: Requires manual dispatch management (creating, superseding,
  expiring). Dispatch automation (Phase 6) mitigates this.

### D8: Sandape Owner PR-Only Bypass

**Decision**: The Sandape Owner (or explicitly delegated Codex, case-by-case)
may bypass the human non-author approval requirement using PR-only bypass.
Direct push bypass remains forbidden under all circumstances.

**Bypass conditions**:

1. **PR-only**: The change must still go through a PR (Draft or Ready).
   Direct push is never permitted.
2. **Explicit reason**: The PR body or a comment must state why the bypass
   is necessary.
3. **Evidence**: Screenshots, logs, or other verifiable evidence must be
   captured in the PR or linked Issue.
4. **Documentation**: The bypass must be recorded before merge for audit.

**Rationale**:
- Some changes (urgent security fixes, trivial metadata updates) don't
  benefit from a second reviewer but still need the audit trail of a PR.
- Direct push bypass would bypass all gates. PR-only bypass preserves the
  audit trail and CI checks while relaxing the review requirement.
- Owner accountability ensures the bypass is used sparingly and only when
  justified.

**Consequences**:
- Positive: Emergency path exists for truly urgent changes.
- Positive: PR-only means CI still runs, and the audit trail is preserved.
- Negative: Risk of overuse. Mitigated by requirement to document reason
  and evidence in every bypass case.

### D9: No Mandatory NekoDreamSensei Reviewer

**Decision**: NekoDreamSensei is not a required reviewer or mandatory
CODEOWNER. They may be `@mentioned` for domain-specific review but are
never a blocker.

**Rationale**: NekoDreamSensei's role is domain-expert consultation, not
delivery gatekeeping. Making them mandatory would create an unnecessary
blocking dependency that slows delivery without proportional quality
benefit.

**Consequences**:
- Positive: Delivery is not blocked by reviewer availability.
- Negative: Domain expertise may be missed if NekoDreamSensei is not
  actively monitoring. Mitigated by allowing PR authors to `@mention` when
  domain review is needed.

### D10: Staged Rollout (Stage-A → Stage-B)

**Decision**: Governance rollout proceeds in two stages:

**Stage-A (active)**:
- Ruleset requires PRs, at least one non-author approval, blocks force push
  and branch deletion.
- Does NOT require green CI (CI is red; Phase 7 will fix it).
- Preflight gate (`scripts/governance/preflight.ps1`) is active.
- SOP, onboarding, and ADR exist (Phase 5a).

**Stage-B (future, Phase 9+)**:
- All Stage-A protections remain.
- Strict Required Checks enabled (CI must be green).
- Conversation resolution required before merge.
- Stale approval protection enabled.
- Squash-only merges.
- Branch auto-delete on merge.
- Drift detection active.

**Rationale**: Stage-A provides immediate protection against the most
dangerous actions (direct push, no-review merges) without requiring CI
green first. Stage-B adds the full protection suite after CI is repaired
and drills are passed.

**Consequences**:
- Positive: Protection starts immediately, not after months of CI repair.
- Positive: Stage-B is only activated after explicit verification (Phase 9
  drills).
- Negative: Stage-A allows merging with red CI. Reviewers must manually
  verify changes until Stage-B.

## Alternatives Considered

### All-in-One Stage-B from Day One

**Pros**: Full protection immediately.

**Cons**: Blocked by pre-existing red CI. Would halt all development until
CI is fixed — a multi-week effort.

**Decision**: Rejected. Stage-A first, Stage-B after CI repair and drills.

### No Owner Bypass — Strict Two-Person Rule for Every PR

**Pros**: Maximum review assurance for every change.

**Cons**: Emergency security fixes would be blocked waiting for a second
reviewer. Trivial governance metadata changes (e.g., updating an AC hash)
would require reviewer overhead disproportionate to the risk.

**Decision**: Rejected. Owner PR-only bypass with documented reason and
evidence provides adequate audit trail for low-risk or urgent changes.

### Direct Push as Allowed Emergency Path

**Pros**: Fastest possible emergency fix.

**Cons**: Bypasses all gates (CI, review, dispatch validation). Destroys
audit trail. Ruleset cannot partially enforce it.

**Decision**: Rejected. PR-only bypass provides sufficient speed for
emergencies while preserving audit trail and CI.

### NekoDreamSensei as Mandatory Reviewer for Governance Changes

**Pros**: Domain expert reviews all governance modifications.

**Cons**: Creates blocking dependency. Slows governance iteration. Not
proportional to risk of most governance changes.

**Decision**: Rejected. Optional `@mention` provides domain review without
blocking dependency.

### File-Based State vs GitHub Issue Parsing for Dispatch

**Pros**: Issue body parsing is simpler — no additional file storage needed.

**Cons**: Issue body is mutable; dispatch state embedded in Issue text can
be edited without authorization. Multiple dispatches for the same Issue
are hard to track. No deterministic file to git-diff.

**Decision**: Use file-based state (`.github/dispatches/<id>.json`).
Issue may *reference* the dispatch but is not the canonical state.

### Single ADR vs Multiple ADRs

**Pros**: One ADR for the entire governance system provides a unified
decision record.

**Cons**: Becomes lengthy. Phase 6 topics (dispatch protocol, gate design)
are complex enough for separate ADRs.

**Decision**: ADR-001 covers Phase 5a decisions. ADR-002 (Phase 6) will
cover the dispatch protocol. ADR-003 (Phase 6) will cover gate design.
This keeps each ADR focused and reviewable.

## Risk & Authorization

### Risk Classification

The governance system as a whole is classified **R3** (highest):
- Repository automation writes are **R2** (external side effects).
- Ruleset boundary changes are **R3** (permissions/policy boundaries).
- Documentation-only changes (this ADR, SOP, onboarding) are **R1** or
  **R0** (no external effects).

### Authorization Requirements

| Operation | Risk | Authorization |
|---|---|---|
| Governance docs creation/modification (Phase 5) | R1 | Issue dispatch + PR + non-author review |
| Client adapter files (Phase 5b) | R1 | Issue dispatch + PR + non-author review |
| Issue Forms, PR Template (Phase 6a) | R1 | Issue dispatch + PR + non-author review |
| Dispatch scripts (Phase 6b) | R1 | Issue dispatch + PR + tests |
| Gate scripts (Phase 6c) | R1 | Issue dispatch + PR + tests |
| CI repair (Phase 7) | R1 | Issue dispatch + PR + non-author review |
| Cursor Automation (Phase 8) | R2 | Issue dispatch + PR + CODEOWNERS |
| Ruleset change (Stage-B, Phase 9) | R3 | Codex explicit approval + screenshot evidence |
| Direct push to master | forbidden | — (Ruleset permanently forbids) |

### R2/R3 Authorization Confirmation

This ADR is accepted with the understanding that:

- **R2 operations** (automation writing to repository) require a governance
  Issue, dispatch, PR, and CODEOWNERS review before deployment.
- **R3 operations** (Ruleset changes for Stage-B) require Codex explicit
  case-by-case confirmation with screenshot evidence before and after the
  change. NekoDreamSensei is NOT required as a second approver for R3
  operations on the governance system itself — Codex acceptance with
  visual evidence is sufficient.
- All R2/R3 operations are performed by Codex under explicit authorization,
  not by unattended automation.

## Consequences

### Positive

1. **Single source of truth**: SOP is canonical; clients reference it.
2. **Deterministic gate checks**: AC hashing is platform-independent and
   reproducible.
3. **Clear ownership**: One active dispatch per Issue prevents conflicts.
4. **Progressive rollout**: Stage-A protects now; Stage-B adds full
   protection when ready.
5. **Audit trail**: Every change goes through PR, regardless of urgency.
6. **No blocking dependencies**: NekoDreamSensei is optional; Owner bypass
   provides emergency path.
7. **SpecKit compatible**: Stable paths and pointer preserved.

### Negative

1. **Process overhead**: Every change, even trivial ones, requires Issue,
   dispatch, PR, and merge. Mitigated by template automation (Phase 6).
2. **Two-stage complexity**: Teams must understand which protections are
   active (Stage-A) and which are coming (Stage-B).
3. **Manual dispatch management**: Until Phase 6, dispatches are managed
   manually in Issue bodies rather than via automated scripts.
4. **Red CI tolerated**: Stage-A accepts red CI; reviewers must compensate.

### Mitigations

| Risk | Mitigation |
|---|---|
| Process overhead | Templates and automation (Phase 6) reduce manual overhead |
| Stage confusion | SOP clearly marks active vs future protections |
| Manual dispatch | Phase 6 dispatch automation addresses this |
| Red CI reliance | Phase 7 CI repair; reviewers verify changes manually until then |
| Bypass overuse | Documentation requirement provides audit trail |

## Related Documents

| Document | Path | Relationship |
|---|---|---|
| Delivery SOP | [../engineering/delivery-sop.md](../engineering/delivery-sop.md) | Normative workflow implementing these decisions |
| Team Onboarding | [../engineering/team-onboarding.md](../engineering/team-onboarding.md) | Setup guide referencing SOP |
| AGENTS.md | [../../AGENTS.md](../../AGENTS.md) | Agent routing (Phase 5b simplification pending) |
| ADR-001 (Documentation Structure) | [./ADR-001-documentation-structure.md](./ADR-001-documentation-structure.md) | Established specs/ as canonical requirements source |
| REQ-064 Spec | [../../specs/064-delivery-governance/](../../specs/064-delivery-governance/) | Full specification and contracts |
| Dispatch Envelope Contract | [../../specs/064-delivery-governance/contracts/dispatch-envelope.md](../../specs/064-delivery-governance/contracts/dispatch-envelope.md) | Dispatch data contract |
| Governance State Gate Contract | [../../specs/064-delivery-governance/contracts/governance-state-gate.md](../../specs/064-delivery-governance/contracts/governance-state-gate.md) | PR Gate behavior contract |
| Handoff Invariants Contract | [../../specs/064-delivery-governance/contracts/handoff-invariants.md](../../specs/064-delivery-governance/contracts/handoff-invariants.md) | Handoff protocol and invariants |

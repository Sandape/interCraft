# Contract: Handoff Invariants (REQ-064)

**Owner**: Codex (supervising acceptance authority)
**Implemented in**: Phase 6 (dispatch.ps1 and gate.ps1)

## Purpose

Define the invariants governing transfer (handoff) of a Dispatch from one Driver to another, or from one phase to the next. These invariants prevent stale or conflicting work from reaching `master`.

## Handoff Triggers

A handoff occurs when:

1. **Driver change**: The `driver` field in the dispatch envelope changes (e.g., from `claude-code` to `codex`)
2. **Issue content change**: The Issue's acceptance criteria text is edited, changing its `ac_hash`
3. **Phase advancement**: The previous phase's PR has been merged, and the next phase begins
4. **Base SHA change**: `master` advances beyond the dispatch's `base_sha`

## Invariant Rules

### Invariant H1: Handoff Invalidates Previous Dispatch

When a handoff occurs, the previous dispatch MUST be marked `superseded` (driver change) or `expired` (base/AC change).

```text
# On new dispatch with same spec_task_id but different driver:
1. Read existing dispatch for (spec_task_id, driver=OLD)
2. Mark it state=superseded
3. Create new dispatch with state=active
4. Write superseded timestamp to old dispatch file
```

### Invariant H2: Gate Rejects Superseded Dispatch

The PR Gate MUST reject any PR referencing a dispatch with `state=superseded` or `state=expired`.

```text
GATE_DISPATCH_INACTIVE: "Dispatch req-064-spec-20260712-01 is superseded by req-064-spec-20260712-02"
```

### Invariant H3: Same Issue, At Most One Active PR

At any time, at most one PR for a given Issue can pass the Gate. If PR-A is open and PR-B is created for the same Issue:

1. PR-B's Gate check: fails with `GATE_DUPLICATE_PR` if the same dispatch is used
2. If PR-B has a new dispatch (superseding PR-A's dispatch): only PR-B can pass the Gate

### Invariant H4: AC Hash Determines Acceptance Criteria

The `ac_hash` in the dispatch envelope MUST be the SHA-256 digest of the Issue's acceptance criteria text. If the Issue is edited:

1. The old dispatch becomes `expired` (AC hash mismatch)
2. A new dispatch must be issued with the updated `ac_hash`
3. Any PR referencing the old dispatch fails the Gate at check D4

### Invariant H5: Base Freshness

The dispatch's `base_sha` must be an ancestor of `master` HEAD for the PR to pass the Gate.

```text
git merge-base --is-ancestor <base_sha> origin/master
```

If this check fails, the dispatch is `expired` and a new dispatch with an updated `base_sha` must be issued.

### Invariant H6: Path Escrow

A dispatch's `allowed_paths` cannot be broadened after creation. A new dispatch with broader paths supersedes the old one.

### Invariant H7: Phase Ordering

Phases MUST execute in numerical order (5 → 6 → 7 → 8 → 9 → 10). A PR for Phase N+1 must not be opened until Phase N's PR is merged.

```text
# Simplified check: does the phase N deliverable exist on master?
git merge-base --is-ancestor <phase-N-merge-sha> master
```

## Handoff Protocol

When a handoff is needed (e.g., Claude Code → Codex):

```text
1. Current driver completes and pushes current work to Draft PR
2. Current driver comments on Issue: "Handoff to <new-driver> for <reason>"
3. Codex (or authorized actor) creates new dispatch with:
   - New dispatch_id
   - New driver
   - Same spec_task_id, base_sha, AC hash (unless changed)
   - state=active
4. Old dispatch is marked superseded
5. New driver creates new branch or reuses existing branch with new dispatch
6. PR Gate validates new dispatch
```

## Evidence of Handoff

Each handoff MUST leave the following evidence:

- Old dispatch file with `state=superseded` and `superseded_by` field
- New dispatch file with `state=active`
- Issue comment documenting the handoff reason

## Rollback During Handoff

If a handoff causes issues:

1. Reactivate old dispatch (change state back to `active`) ONLY if no PR from new dispatch has merged
2. If a new PR merged, revert it: `git revert -m 1 <merge-sha>`
3. Gate will accept old dispatch's PR again
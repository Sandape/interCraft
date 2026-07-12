# Contract: Handoff Invariants (REQ-064)

**Owner**: Codex (supervising acceptance authority)
**Implemented in**: Phase 6 (dispatch.ps1 and gate.ps1)

## Purpose

Define the invariants governing transfer (handoff) of a Dispatch from one Driver to another, or from one phase to the next. These invariants prevent stale or conflicting work from reaching `master`.

## Handoff Triggers

A handoff occurs when:

1. **Driver change**: The `driver` field in the dispatch envelope changes (e.g., from `claude-code` to `codex`)
2. **Issue content change**: The Issue's canonical acceptance criteria field is edited, changing its `ac_hash`
3. **Phase advancement**: The previous phase's PR has been merged, and the next phase begins
4. **Base SHA change**: `master` advances beyond the dispatch's `base_sha` (authoritative remote `master` HEAD via `gh api`, not stale local ref)

## Invariant Rules

### Invariant H1: Handoff Invalidates Previous Dispatch

When a handoff occurs, the previous dispatch MUST be marked `superseded` (driver change) or `expired` (base/AC change).

```text
# On new dispatch for the same issue_number/execution target:
1. Read the current active dispatch for issue_number
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

The `ac_hash` in the dispatch envelope MUST be the SHA-256 digest of the versioned canonical acceptance statement defined by the Dispatch Envelope contract. If that statement is edited:

1. The old dispatch becomes `expired` (AC hash mismatch)
2. A new dispatch must be issued with the updated `ac_hash`
3. Any PR referencing the old dispatch fails the Gate at check D4

### Invariant H5: Base Freshness (Deterministic)

Dispatch `base_sha` MUST equal authoritative remote `master` HEAD at dispatch creation time AND at Gate validation time. PR HEAD MUST descend from `base_sha`.

```text
# Use authoritative remote state, NOT stale local origin/master
gh api repos/:owner/:repo/git/ref/heads/master --jq '.object.sha'

# Verify:
#   1. base_sha == authoritative_master_sha  (both at dispatch time and Gate time)
#   2. git merge-base --is-ancestor base_sha PR_HEAD  (PR descends from base)
```

If `master` advances between dispatch creation and Gate validation, the dispatch is `expired`. MUST issue a new dispatch with the latest `master` SHA as `base_sha`, and rebase the PR onto the new base. Never rely on stale local `origin/master` — always verify via `gh api` when local transport is unavailable.

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

1. MUST NOT reactivate expired or superseded dispatch. Instead, issue a fresh dispatch (new `dispatch_id`) with revalidated `base_sha`, `ac_hash`, and `allowed_paths`, set `state=active`.
2. If a PR from the new dispatch has already squash-merged and needs reversal,
   create a rollback Issue and fresh dispatch/branch from authoritative
   `master`, then run `git revert <squash-merge-sha>` without `-m`; verify and
   deliver the inverse change through a new Draft PR. Never push the revert
   directly to `master`.
3. Create a new branch or reuse existing branch with the fresh dispatch
4. PR Gate validates the fresh dispatch — on pass, work can proceed

**Why no reactivation**: An expired/superseded dispatch's `base_sha` may no longer equal authoritative `master` HEAD, and its `ac_hash` may not reflect the current canonical AC field. Reactivating it would bypass the deterministic freshness guarantee and could allow stale or conflicting work to proceed.

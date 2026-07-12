# Contract: Governance State & PR Gate (REQ-064)

**Owner module**: `scripts/governance/gate.ps1`
**Caller**: CI workflow or manual PR validation
**Implemented in**: Phase 6

## Purpose

Define the Governance State tracking and PR Gate checking behavior. The Gate ensures that only authorized, valid, and non-conflicting PRs can proceed toward merge.

## Governance State

The governance state tracks the current active phases and dispatches:

| Field | Type | Description |
|---|---|---|
| `current_phase` | int | Current governance phase (5–10) |
| `active_dispatches` | dispatch_envelope[] | Currently active dispatch envelopes |
| `completed_phases` | int[] | Phases whose PR has been merged |
| `governance_version` | string | Active governance system version |

State is maintained by convention (the set of merged PRs + active dispatch files). No centralized state file needed at this stage.

## PR Gate Check List

The PR Gate MUST run these checks in order, fail-closed on first failure:

### 1. General Checks (always run)

| # | Check | Fail Condition | HTTP/Fail Code |
|---|---|---|---|
| G1 | Branch targets `master` | PR base ref ≠ `refs/heads/master` | `GATE_INVALID_TARGET` |
| G2 | PR is Draft or Ready | — | (informational) |
| G3 | PR body has `Refs #N` | Missing or malformed | `GATE_MISSING_ISSUE_REF` |

### 2. Dispatch Validation

| # | Check | Fail Condition | Fail Code |
|---|---|---|---|
| D1 | Issue exists and is open | Issue #N not found or closed | `GATE_ISSUE_NOT_OPEN` |
| D2 | Dispatch envelope exists | No `.github/dispatches/<id>.json` | `GATE_DISPATCH_NOT_FOUND` |
| D3 | Dispatch state is `active` | State is `superseded` or `expired` | `GATE_DISPATCH_INACTIVE` |
| D4 | AC hash matches canonical AC field | Envelope `ac_hash` ≠ sha256(normalized canonical AC field from `## Acceptance Criteria` or `### AC` section) | `GATE_AC_HASH_MISMATCH` |
| D4a | Canonical acceptance statement well-formed | Versioned canonical statement missing, duplicated, empty, or malformed per Dispatch Envelope normalization contract | `GATE_AC_MALFORMED` |

### 3. Path Validation

| # | Check | Fail Condition | Fail Code |
|---|---|---|---|
| P1 | All changed paths in `allowed_paths` | Any changed file outside allowed globs | `GATE_PATH_ESCAPE` |
| P2 | No changes to singleton paths without governance Issue | `.specify/feature.json`, `.github/**`, `AGENTS.md` etc. | `GATE_SINGLETON_VIOLATION` |

### 4. Freshness & Uniqueness

| # | Check | Fail Condition | Fail Code |
|---|---|---|---|
| F1 | Dispatch base_sha equals authoritative master HEAD | `gh api` master ref SHA ≠ envelope base_sha (never use stale local origin/master) | `GATE_BASE_NOT_AUTHORITATIVE` |
| F1a | PR head descends from base_sha | `git merge-base --is-ancestor base_sha PR_HEAD` fails | `GATE_BASE_STALE` |
| F2 | No other open PR for same Issue | Another open PR references same Issue # | `GATE_DUPLICATE_PR` |
| F3 | Governance version matches | Envelope version ≠ `scripts/governance/version.txt` | `GATE_GOV_VERSION_MISMATCH` |

### 5. Evidence Checks (Phase 9+)

| # | Check | Fail Condition | Fail Code |
|---|---|---|---|
| E1 | Evidence directory exists (if spec requires) | Missing `docs/evidence/<req-id>/` | `GATE_MISSING_EVIDENCE` |

## Fail-Closed Semantics

```text
gate.ps1 -IssueNumber 19 -PRNumber 42 -DispatchId "req-064-spec-20260712-01"
```

- Returns exit code 0 when ALL checks pass
- Returns exit code >0 and writes `GATE_*` code and human-readable message on first failure
- Writes structured JSON result to stdout:
  ```json
  {"passed": false, "failed_check": "GATE_AC_HASH_MISMATCH", "message": "AC hash ... does not match Issue #19 body"}
  ```

## Concurrency Guarantee

GitHub cannot prevent two local clients from starting work simultaneously. The Gate guarantees:

1. At most one PR per active dispatch (`GATE_DUPLICATE_PR`)
2. Concurrency key = `(dispatch_id)` — automated workflows serialize on this key
3. Assignee/labels are NOT used as atomic locks — only dispatch file + Gate check

## Integration Points

| Checkpoint | Script | When |
|---|---|---|
| Pre-commit | `preflight.ps1` | Before every commit |
| PR open/sync | `gate.ps1` | CI workflow on `pull_request` event |
| PR merge | Ruleset (Required Check) | Before squash merge |

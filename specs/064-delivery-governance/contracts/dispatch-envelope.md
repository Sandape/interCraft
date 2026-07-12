# Contract: Dispatch Envelope (REQ-064)

**Owner module**: `scripts/governance/dispatch.ps1`
**Issued by**: Codex (supervising acceptance authority)
**Implemented in**: Phase 6

## Purpose

Define the canonical shape of a Dispatch Envelope — the immutable record authorizing one execution unit of governance or feature work. Every PR must reference a valid, non-expired dispatch envelope to pass the PR Gate.

## Dispatch Envelope Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `dispatch_id` | string | yes | Unique identifier, format: `<req-prefix>-<purpose>-<yyyymmdd>-<nn>` |
| `driver` | string | yes | Actor executing the work: `claude-code`, `codex`, `cursor`, `human` |
| `issue_number` | integer | yes | GitHub Issue number this dispatch is associated with |
| `base_sha` | string | yes | Full SHA of authoritative remote `master` at dispatch time — MUST equal `gh api repos/:owner/:repo/git/ref/heads/master` result |
| `spec_task_id` | string | yes | Reference to canonical spec or task ID, e.g. `REQ-064`, `T101` |
| `ac_hash` | string | yes | SHA-256 hex digest of the canonical acceptance criteria field (not entire Issue body) |
| `canonical_ac_text_version` | string | yes | Normalization version identifier, e.g. `v1`; records which canonical statement and normalization rules were used |
| `allowed_paths` | string[] | yes | Glob patterns specifying which files this dispatch may create/modify |
| `governance_version` | string | yes | Governance system version, e.g. `stage-a-owner-pr-bypass-v1` |
| `created_at` | string (ISO 8601) | yes | Timestamp of dispatch creation |
| `state` | string | yes | `active` \| `superseded` \| `expired` |

## State Machine

```
                 ┌──────────────┐
                 │   active     │
                 └──────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
   ┌──────────┐  ┌────────────┐  ┌──────────┐
   │superseded│  │  expired   │  │(remains  │
   │(by new   │  │(base SHA   │  │ active)  │
   │ dispatch)│  │ diverged   │  │          │
   └──────────┘  └────────────┘  └──────────┘
```

### Transitions

1. **active → superseded**: A new dispatch with the same `issue_number` but different `dispatch_id` is issued. Old dispatch is superseded.
2. **active → expired**: Dispatch `base_sha` no longer equals authoritative remote `master` HEAD (verified via `gh api repos/:owner/:repo/git/ref/heads/master`, never stale local `origin/master`), OR PR HEAD does not descend from `base_sha`, OR Issue canonical AC field hash no longer matches envelope `ac_hash`. If `master` advances, dispatch expires — MUST issue new dispatch and rebase PR.
3. **active → (stays active)**: At most one PR per active dispatch. PR Gate rejects second PR for same dispatch.
4. **Expired/superseded → any**: FORBIDDEN. An expired or superseded dispatch MUST NOT be reactivated under any circumstance. To resume work, issue a fresh dispatch with a new `dispatch_id` after revalidation.

## Validation Rules

1. `dispatch_id` MUST be globally unique (past dispatches stored in `.github/dispatches/`)
2. `ac_hash` MUST equal `sha256(<canonical acceptance statement>)`, not the mutable checkbox list or entire Issue body. Version `v1` selects exactly one heading whose trimmed text case-insensitively equals `Canonical Acceptance Statement`; its content ends at the next heading of the same or higher level. Normalization is UTF-8, Unicode NFC, CRLF/CR converted to LF, leading/trailing whitespace stripped per line, and trailing blank lines removed. Digest is lowercase hex SHA-256. Missing, duplicated, empty, or malformed canonical statements MUST fail closed (`GATE_AC_MALFORMED`). Checking acceptance boxes or adding comments MUST NOT change this hash.
3. `allowed_paths` MUST be a subset of the originating Issue's allowed paths
4. `base_sha` MUST exactly equal authoritative remote `master` HEAD at dispatch creation time, verified via `gh api repos/:owner/:repo/git/ref/heads/master`. At Gate validation time, `base_sha` MUST still equal the current authoritative `master` HEAD, and PR HEAD MUST descend from `base_sha` (`git merge-base --is-ancestor base_sha PR_HEAD`).
5. `governance_version` MUST match the currently active governance version constant

## File Storage

Dispatch envelopes are stored as JSON files in `.github/dispatches/`:

```json
{
  "dispatch_id": "req-064-spec-20260712-01",
  "issue_number": 19,
  "driver": "claude-code",
  "base_sha": "880580a088ecf0186fddcb64c46edd48e60043d7",
  "spec_task_id": "REQ-064 / Phase 4 Spec-only",
  "ac_hash": "1323039b18760a909e22100e0a62aa8864011a0b9424e41dcb2653bdab805b56",
  "canonical_ac_text_version": "v1",
  "allowed_paths": [
    "specs/README.md",
    "specs/064-delivery-governance/**"
  ],
  "governance_version": "stage-a-owner-pr-bypass-v1",
  "created_at": "2026-07-12T00:00:00Z",
  "state": "active"
}
```

## Invariants

1. At most one dispatch with `state=active` per Issue/execution target (`issue_number`) regardless of driver. Two different drivers MUST NOT each hold an active dispatch for the same Issue.
2. An expired or superseded dispatch MUST NOT be reactivated under any circumstance. To resume work, issue a fresh dispatch with a new `dispatch_id` after revalidation of `base_sha`, `ac_hash`, and `allowed_paths`.
3. `base_sha` is write-once: never modified after creation
4. File path: `.github/dispatches/<dispatch_id>.json`
5. `issue_number` is immutable after creation — a dispatch always references its original Issue

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
| `base_sha` | string | yes | Full SHA of `master` at dispatch time — PR must be at or ahead of this |
| `spec_task_id` | string | yes | Reference to canonical spec or task ID, e.g. `REQ-064`, `T101` |
| `ac_hash` | string | yes | SHA-256 hex digest of the Issue's acceptance criteria text |
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

1. **active → superseded**: A new dispatch with the same `spec_task_id` but different `dispatch_id` is issued. Old dispatch is superseded.
2. **active → expired**: Base SHA is no longer ancestral to `master` HEAD (forced by `git merge-base --is-ancestor`), OR Issue AC hash no longer matches current Issue body.
3. **active → (stays active)**: At most one PR per active dispatch. PR Gate rejects second PR for same dispatch.

## Validation Rules

1. `dispatch_id` MUST be globally unique (past dispatches stored in `.github/dispatches/`)
2. `ac_hash` MUST equal `sha256(<current Issue acceptance criteria text>)`
3. `allowed_paths` MUST be a subset of the originating Issue's allowed paths
4. `base_sha` MUST be an ancestor of the PR branch's target (usually `master`)
5. `governance_version` MUST match the currently active governance version constant

## File Storage

Dispatch envelopes are stored as JSON files in `.github/dispatches/`:

```json
{
  "dispatch_id": "req-064-spec-20260712-01",
  "driver": "claude-code",
  "base_sha": "880580a088ecf0186fddcb64c46edd48e60043d7",
  "spec_task_id": "REQ-064 / Phase 4 Spec-only",
  "ac_hash": "1323039b18760a909e22100e0a62aa8864011a0b9424e41dcb2653bdab805b56",
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

1. At most one dispatch with `state=active` per `(driver, spec_task_id)` tuple
2. An expired dispatch cannot be reactivated
3. `base_sha` is write-once: never modified after creation
4. File path: `.github/dispatches/<dispatch_id>.json`
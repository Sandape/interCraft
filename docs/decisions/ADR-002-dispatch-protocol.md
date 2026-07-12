# ADR-002: Dispatch Protocol

## Status

Accepted (Phase 6b)

## Date

2026-07-12

## Context

[ADR-001](./ADR-001-multi-client-delivery-governance.md) established that
every execution unit requires a dispatch envelope — an immutable record
authorizing one unit of governance or feature work. ADR-001 deferred the
concrete dispatch format, state machine, file storage, and validation
protocol to Phase 6.

This ADR captures the architecture decisions for the Phase 6b dispatch
protocol:

1. **Dispatch envelope format and validation** (field-level contract)
2. **State machine transitions** with terminal-state semantics
3. **Canonical Acceptance Criteria (AC) v1 normalization** for deterministic
   hashing
4. **Allowed-path parsing and validation** against Issue-sourced scope
5. **Authoritative remote verification** via `gh api` (never stale local
   `origin/master`)
6. **Locking, atomicity, and crash recovery** for concurrent-safe mutations
7. **Trust boundaries** between Issue body (untrusted input), dispatch file
   (authoritative state), and `gh api` (remote truth)

## Decision

### D1: Dispatch Envelope — File-Based State Machine

**Decision**: Store dispatch envelopes as individual JSON files under
`.github/dispatches/<dispatch_id>.json`. The file name == the `dispatch_id`
acts as the uniqueness anchor. A `.json.example` file is provided as
documentation; it is never scanned as live state.

**Rationale**: File-based state is git-visible, diffable, and does not
depend on GitHub Issue mutability. Issue body parsing is used for AC
extraction and allowed-path scoping at *creation time*, but the dispatch
file is the authoritative state record thereafter.

**States**: `active` → `superseded` | `expired`. Terminal states are
permanently terminal — no operation may reactivate a superseded or expired
dispatch.

### D2: Envelope Fields

All 11 fields from the dispatch envelope contract. Key invariants:

| Field | Mutability | Validation |
|---|---|---|
| `dispatch_id` | Write-once | Globally unique, lowercase, and filename-safe; format `<req-prefix>-<purpose>-<yyyymmdd>-<nn>` |
| `driver` | Write-once | Must be one of `claude-code`, `codex`, `cursor`, `cursor-automation`, `human` |
| `issue_number` | Write-once | Integer; immutable after creation |
| `base_sha` | Write-once | Must equal authoritative remote `master` HEAD at creation time |
| `spec_task_id` | Write-once | e.g. `REQ-064`, `T101` |
| `ac_hash` | Write-once | SHA-256 hex of v1-normalized canonical AC text |
| `canonical_ac_text_version` | Write-once | `v1` |
| `allowed_paths` | Write-once | Repository-relative globs; subset of Issue `Requested Allowed Paths` |
| `governance_version` | Write-once | Must match active governance version |
| `created_at` | Write-once | ISO 8601 UTC |
| `state` | Mutable | `active` → `superseded` | `expired` |

### D3: State Machine — Singleton Per Issue

**Decision**: At most one dispatch with `state=active` per `issue_number`,
regardless of `driver`. Ordinary `Create` fails when an active dispatch already
exists; this prevents a second client from silently stealing the Issue.
Replacement requires the explicit `Supersede` parameter set with the complete
new envelope inputs.

```
Create: verify no active for Issue → write new active
Supersede: revalidate remote/Issue/new inputs → verify exactly one expected
  active → write old state=superseded → write new active
Expire:  read current → verify active → write state=expired
Validate: read file → check active → re-fetch remote → re-hash AC →
  check paths → check no duplicate active → report
```

**Terminal-state invariant**: Supersede and Expire both reject calls on
already-terminal dispatches. Create rejects if the caller tries to reuse
a `dispatch_id` that already exists (even if terminal), ensuring globally
unique IDs.

### D4: Canonical Acceptance Criteria v1 Normalization

**Decision**: The AC heading is located by scanning the Issue body for any
line matching `/^(#+)\s+(.+)$/` where the trimmed heading text
case-insensitively equals `Canonical Acceptance Statement`. Unlike the
earlier SOP draft that specified `##`, the implementation accepts *any*
heading level (`#`, `##`, `###`, etc.) and ends content at the next heading
of the same or higher level (same number of `#` or fewer). Headings inside
backtick or tilde code fences are ignored. Deeper headings are part of the
selected canonical text, including their Markdown heading line.

**Normalization pipeline**:
1. Extract content (lines after heading, excluding the heading itself)
2. Remove trailing blank lines from content
3. Join remaining lines with `\n`
4. Apply Unicode NFC normalization
5. Convert CRLF and CR to LF
6. Strip leading and trailing whitespace on every line
7. Remove trailing blank lines
8. Encode as UTF-8 without BOM
9. Compute SHA-256, output as lowercase hex

**Mutations to non-AC sections** (checkboxes, comments, templates) do not
change the hash. Missing, duplicated, empty, or malformed AC headings cause
an immediate fail-closed error. Per v1, leading blank content lines are
preserved; only trailing blank lines are removed.

### D5: Allowed-Path Parsing and Validation

**Decision**: The Issue `Requested Allowed Paths` heading is parsed using
the same syntax as the preflight gate's `ConvertTo-RepositoryPath`:

- The heading is mandatory, unique, and non-empty. Missing, duplicate, or
  malformed content fails closed; absence never means unlimited scope.
- Lines may be raw Issue Form textarea values or Markdown bullets, with
  optional surrounding backticks.

- Permitted: repository-relative exact paths (e.g., `scripts/governance/`)
  and trailing `/**` directory globs (e.g., `src/**`)
- Rejected: absolute paths, path traversal (`.` or `..`), `.git` metadata,
  Windows alternate data streams (colons), control characters (ASCII < 32
  or 127), unsupported wildcards (`*`, `?`, `[`, `]` before trailing `/**`)

**Dispatch creation** requires the caller-supplied `allowed_paths` to be a
subset of the Issue's parsed `Requested Allowed Paths`. The dispatch's paths
are independently validated and deduplicated. Matching is ordinal and
case-sensitive because GitHub repository paths are case-sensitive.

**Supersede path safety**: On supersede (creating a new dispatch for the
same Issue), the new dispatch's `allowed_paths` must still be a subset of
the freshly-fetched Issue's `Requested Allowed Paths`. This means supersede
can never broaden scope beyond what the Issue currently allows. If the
Issue body was updated to include more paths since the original dispatch,
the superseding dispatch can use those new paths — but only because the
re-fetched Issue body explicitly contains them.

### D6: Authoritative Remote Verification — Fail Closed on Transport Loss

**Decision**: Create, Supersede, and Validate fetch both the authoritative
`master` HEAD and the Issue body via
`gh api repos/:owner/:repo/git/ref/heads/master` and
`gh api repos/:owner/:repo/issues/<number>` respectively.

- On non-zero exit, invalid JSON, or missing required fields: **fail closed**.
  The operation does not proceed, does not fall back to stale local
  `origin/master`, and does not weaken TLS/certificate checks.
- The caller (the dispatch script) does not accept a `-BaseSha` or `-AcHash`
  parameter to override these values. No production bypass parameter exists
  that accepts caller-supplied authoritative values.
- Tests use a fake `gh` command on `PATH` to simulate GitHub API responses.
  The test fake is the *only* mechanism for supplying test values.
- Expire is a local terminal-state mutation with an explicit reason; it cannot
  create or reactivate authority. Subsequent use still requires a fresh Create
  and full remote validation.

### D7: Concurrency, Locking, and Atomicity

**Decision**: All mutations acquire an exclusive file lock on
`.github/dispatches/.lock` before reading or writing any dispatch state.

**Lock protocol**:
1. Open `.lock` with `FileMode.CreateNew` (fails atomically if lock held)
2. Retry up to 10 times with 200 ms delay between attempts
3. Fail closed if `.tmp` or `.bak` recovery artifacts exist
4. All mutation reads and writes happen while the owned lock is held
5. Only the process that successfully acquired the lock may delete it

**Atomic write protocol**:
1. Write UTF-8-no-BOM content to a GUID-suffixed same-volume temp file
2. For a new envelope, atomically move temp to the non-existing JSON path
3. For a state transition, use `File.Replace` with a GUID-suffixed backup;
   never delete the target before replacement
4. Clean artifacts owned by caught, unambiguous failures; preserve ambiguous
   backup state for explicit recovery

**Supersede crash semantics**: The order of operations is:
1. Lock acquired
2. If existing active dispatch for the Issue exists:
   a. Write superseded version of old dispatch atomically
3. Write new dispatch atomically
4. Lock released

If step 3 fails after step 2a succeeded, the old dispatch is superseded but
the new dispatch was never written. The Issue has no active dispatch — an
operator must inspect recovery artifacts, re-fetch remote truth, and issue a
brand-new `Create` with a new ID. This is preferred over the alternative (new
written first, then old superseded), which could leave two active dispatches
if the supersede write fails. The old terminal dispatch is never reactivated.

**Hard-crash recovery**: A killed process can leave `.lock`, `.tmp`, or `.bak`.
`finally` does not run after every hard crash. Later operations detect these
artifacts and fail closed; they never delete them based only on age. An operator
must confirm no writer is active, inspect the target/temp/backup relationship,
preserve evidence, and perform explicit recovery before retrying with a fresh
ID when required.

### D8: Trust Boundaries

| Input Source | Trust Level | Handling |
|---|---|---|
| `gh api` master ref response | High (authenticated) | Used as ground truth for `base_sha` |
| `gh api` Issue response body | Untrusted | Parsed for AC heading and allowed paths; validated with strict rejection |
| Caller parameters (`-Driver`, `-DispatchId`, etc.) | Authenticated caller | Validated for format; `allowed_paths` validated against Issue scope |
| Existing dispatch files on disk | Authoritative state | Read-only after initial creation; never overwritten except by authorized mutations |

### D9: Rollback

**Decision**: Dispatch state mutations are governed PR changes. If a dispatch
operation needs reversal (e.g., a dispatch was created with wrong paths):

1. Create a new governance Issue and fresh dispatch from authoritative `master`
2. Create a rollback branch: `codex/<req>-rollback-<purpose>`
3. Run `git revert <squash-merge-sha>` (without `-m` — squash commits have
   one parent)
4. Verify the inverse diff and run tests
5. Open a Draft PR and follow the standard review/merge path

Direct dispatch file edits (bypassing `dispatch.ps1`) are forbidden. The
script is the sole authorized writer to `.github/dispatches/`.

### D10: Example File — Not Live State

**Decision**: The directory contains `example.dispatch.json.example`. The
`.json.example` extension:

1. Excludes the file from glob-based scans of live dispatch state
2. Makes the non-authoritative intent explicit at a filename level
3. Contains `dispatch_id: "EXAMPLE-NOT-AUTHORITATIVE"` and `state: "expired"`
   as additional safety markers
4. Is syntactically valid JSON so validation tools don't choke if pointed at
   the directory

## Alternatives Considered

### Single JSON State File vs Per-Dispatch Files

**Decision**: Per-dispatch files. Rationale: git-diff per dispatch, no merge
conflicts on concurrent creates for different Issues, natural uniqueness
enforcement.

### GitHub Issue as Sole State

**Decision**: Rejected. Issue body is mutable; embedded state can be edited
without authorization. File-based state is the authoritative record.

### Production Bypass Parameter for Authoritative Values

**Decision**: Rejected. A production bypass parameter (e.g., `-OverrideBaseSha`)
would be a security hole — any caller could supply arbitrary values and bypass
the authoritative `gh api` check. Tests use a fake `gh` on `PATH` instead.

### Lock-Free Operations

**Decision**: Rejected. Without a lock, concurrent `Create` calls for the
same Issue could race and both succeed, violating the singleton invariant.

## Consequences

### Positive

1. **Deterministic validation**: AC hashing is platform-independent.
2. **Singleton enforcement**: Locking guarantees at most one active dispatch
   per Issue.
3. **Remote authority**: `gh api` eliminates stale-local-ref vulnerabilities.
4. **Crash containment**: Atomic replacement plus fail-closed recovery-artifact
   detection prevents ambiguous state from being treated as valid authority.
5. **Testable isolation**: Fake `gh` on PATH enables full offline testing.
6. **Git-visibility**: Per-dispatch files are diffable and auditable.

### Negative

1. **Lock contention**: Concurrent creates for different Issues wait on the
   same lock file, though the wait is bounded (10 × 200 ms = 2 seconds worst
   case).
2. **gh dependency**: No offline operation possible for mutations. Validate
   also requires remote access.
3. **Crash window**: Supersede failure after old dispatch is deactivated
   leaves the Issue without an active dispatch.

### Mitigations

| Risk | Mitigation |
|---|---|
| Lock contention | Retries are bounded; contention fails explicitly and the caller retries only after refreshing remote state |
| gh dependency | Fail closed with clear error; no fallback to stale refs |
| Crash window | Old remains terminal; inspect artifacts and issue a new ID after full revalidation |
| Lock/temp/backup debris | Fail closed; never age-delete; explicit operator inspection and recovery |

## Related Documents

| Document | Path | Relationship |
|---|---|---|
| Delivery SOP | [../engineering/delivery-sop.md](../engineering/delivery-sop.md) | Canonical workflow; dispatch is step 4.3 |
| ADR-001 | [./ADR-001-multi-client-delivery-governance.md](./ADR-001-multi-client-delivery-governance.md) | Parent ADR establishing dispatch concept |
| Dispatch Envelope Contract | [../../specs/064-delivery-governance/contracts/dispatch-envelope.md](../../specs/064-delivery-governance/contracts/dispatch-envelope.md) | Envelope fields and state machine |
| Handoff Invariants Contract | [../../specs/064-delivery-governance/contracts/handoff-invariants.md](../../specs/064-delivery-governance/contracts/handoff-invariants.md) | Handoff protocol using dispatch state |
| Preflight Gate | [../../scripts/governance/preflight.ps1](../../scripts/governance/preflight.ps1) | Pre-commit gate (Phase 3, active) |
| Delivery SOP §5 | [../engineering/delivery-sop.md#5-dispatch-envelope--ac-normalization](../engineering/delivery-sop.md#5-dispatch-envelope--ac-normalization) | Envelope spec and AC normalization |

# ADR-003: Governance Gate Design

## Status

Accepted (Phase 6c)

## Date

2026-07-12

## Context

[ADR-001](./ADR-001-multi-client-delivery-governance.md) established that every
PR must pass an automated gate before it can proceed toward merge. ADR-001
defined the gate's purpose and high-level checks but deferred the concrete
design to Phase 6.

[ADR-002](./ADR-002-dispatch-protocol.md) defined the dispatch envelope format,
state machine, and validation protocol that the gate depends on for dispatch
integrity checks.

This ADR captures the architecture decisions for the Phase 6c PR Gate
(`scripts/governance/gate.ps1`):

1. **Read-only design** — the gate inspects but never writes GitHub state.
2. **Input parameters** — PR number and dispatch ID are the only
   execution-authority inputs; no caller-supplied SHA/hash/path overrides.
3. **Child-process dispatch validation** — dispatch.ps1 Validate runs as a
   separate `powershell.exe` process and is the sole dispatch integrity
   boundary.
4. **PR-specific checks** — Refs parsing, target branch, base freshness,
   file-path containment, singleton/consumption detection, evidence
   verification.
5. **Deterministic error codes** — every failure produces a GATE_* code.
6. **Stage-A status** — the gate runs but is not yet a required CI check.
   Phase 7 will bind the gate into the CI workflow as a required check before
   Stage-B activation.

## Decision

### D1: Read-Only PR-Scoped Gate

**Decision**: The gate takes only a PR number and a dispatch ID (plus
repository identity). It performs all reads via authenticated `gh api` — no
GitHub writes, no stale `origin/master`, and no authority-override parameters
that let a caller supply base SHA, AC hash, or allowed paths.
The dispatch store is fixed to `.github/dispatches` relative to the gate's
repository root; callers cannot override it.

**Rationale**:
- A read-only gate cannot accidentally mutate GitHub state.
- Fresh `gh api` calls prevent stale-local-ref vulnerabilities.
- No bypass parameter means every check goes through authoritative sources.

**Consequences**:
- Positive: No risk of accidental writes from the gate.
- Positive: Every call to the gate verifies the current state of `master`,
  the Issue, and the dispatch — never a stale snapshot.
- Negative: The gate requires network access to GitHub. If `gh` is
  unavailable, the gate cannot pass. This is acceptable because the gate runs
  in CI where `gh` is always available.

### D2: Child-Process Dispatch Validation Boundary

**Decision**: The gate calls `dispatch.ps1 -Validate` as a child
`powershell.exe` process and maps its DISPATCH_* error codes to GATE_* error
codes. The gate does not duplicate dispatch validation logic.

**Rationale**:
- `dispatch.ps1 Validate` is the canonical dispatch integrity checker. It
  verifies the envelope file is valid JSON, has all required fields, matches
  current governance version, confirms the dispatch is `active`, re-fetches
  authoritative `master` SHA, re-computes the AC hash from the live Issue,
  verifies allowed paths against the Issue, and checks no duplicate active
  dispatch exists for the same Issue.
- Forking this logic in the gate would create a second, potentially divergent
  code path.
- The child-process boundary is fakeable in tests by copying the gate beside a
  test-only sibling `dispatch.ps1` and placing a fake `gh` command on PATH.

**Error mapping**:

| dispatch.ps1 error | Gate error |
|---|---|
| DISPATCH_NOT_FOUND | GATE_DISPATCH_NOT_FOUND |
| DISPATCH_CORRUPT_STORE / DISPATCH_RECOVERY_REQUIRED / DISPATCH_LOCK_FAILED | GATE_DISPATCH_CORRUPT |
| DISPATCH_INACTIVE | GATE_DISPATCH_INACTIVE |
| DISPATCH_ISSUE_MISMATCH | GATE_MISSING_ISSUE_REF |
| DISPATCH_GH_API_FAILED | GATE_TRANSPORT_FAILURE |
| DISPATCH_BASE_STALE | GATE_BASE_NOT_AUTHORITATIVE |
| DISPATCH_AC_HASH_MISMATCH | GATE_AC_HASH_MISMATCH |
| AC_MALFORMED / PATHS_MALFORMED | GATE_AC_MALFORMED |
| DISPATCH_INVALID_GOVERNANCE_VERSION | GATE_GOV_VERSION_MISMATCH |
| DISPATCH_ISSUE_CLOSED | GATE_ISSUE_NOT_OPEN |
| DISPATCH_PATH_ESCAPE | GATE_PATH_ESCAPE |
| DISPATCH_DUPLICATE_ACTIVE | GATE_DUPLICATE_PR |

**Consequences**:
- Positive: Single code path for dispatch integrity — any fix or improvement
  to `dispatch.ps1 Validate` applies to the gate automatically.
- Positive: Tests can independently test dispatch validation and gate logic.
- Negative: The gate has a child-process dependency on the sibling
  `dispatch.ps1`. Production callers cannot override that path. Tests isolate
  both scripts in a temporary directory and replace only the sibling validator
  inside that test directory.
- Stage-B condition: Phase 7 must execute `gate.ps1` and its sibling validator
  from an authoritative `master` checkout, separate from PR-controlled files,
  and must provide the dispatch store through an authenticated durable source.
  Running the gate from the PR checkout is not a security boundary.

### D3: Input Trust Boundaries

**Decision**: The gate distinguishes three input trust levels:

| Source | Trust | Usage |
|---|---|---|
| `gh api` responses | **High** (authenticated) | Ground truth for master SHA, PR metadata, Issue state, file list |
| Dispatch envelope on disk | **Authoritative** | Allowed paths, base SHA, AC hash — validated by dispatch.ps1 |
| PR body text | **Untrusted** | Parsed for Refs #N and Dispatch ID; rejected if malformed |

**Rationale**: The PR body is authored by the PR creator and could be
malformed or misleading. The gate parses it with strict validation — exactly
one `Refs #N`, exactly one structured `Dispatch ID` field matching the
expected identifier. Malformed or non-matching content fails closed.
The referenced API object must be an Issue: an `issues/{N}` response carrying
the GitHub `pull_request` marker is rejected even when it is open.

**Consequences**:
- Positive: A PR with a deliberate malformed Refs or Dispatch field is
  rejected regardless of dispatch validity.
- Positive: The PR's stated Issue and Dispatch must match the envelope's
  recorded Issue and the caller-requested Dispatch ID.
- Negative: The parsing is strict — flexible PR body formats are rejected.

### D4: Conjunctive Base Freshness

**Decision**: Base freshness requires ALL of the following to hold:

1. Envelope `base_sha` equals authoritative `master` HEAD (fetched via
   `gh api repos/:owner/:repo/git/ref/heads/master`).
2. PR `base` SHA equals envelope `base_sha`.
3. GitHub compare API proves the envelope `base_sha` is an ancestor of the
   PR head (compare status is `ahead` or `identical`, not `behind` or
   `diverged`).

**Rationale**: A stale base allows changes based on outdated `master` to
proceed. All three conditions must hold because:
- Condition 1 ensures the dispatch was created from current `master`.
- Condition 2 ensures the PR was created with that dispatch as its base.
- Condition 3 ensures no force-push or rebase has broken ancestry.

**Consequences**:
- Positive: Deterministic freshness guarantee.
- Positive: Uses the compare API which is available to any authenticated
  caller without local git access.
- Negative: If `master` advances between dispatch creation and gate
  validation, the dispatch must be expired and re-created.

### D5: Exact-Ordinal Path Containment

**Decision**: Every changed file in the PR must match an envelope
`allowed_paths` entry using ordinal (case-sensitive) matching. Supported
patterns:

- **Exact path**: `scripts/governance/gate.ps1` matches only that file.
- **Directory glob**: `scripts/governance/**` matches that directory and any
  file or subdirectory under it.

For a GitHub file entry with `status: renamed`, both `filename` (destination)
and `previous_filename` (source) must independently pass the same safety and
allowlist checks. A rename changes two repository paths and cannot be used to
hide an out-of-scope delete behind an in-scope destination.

Rejected paths:
- Traversal (`..`, `.`)
- `.git` metadata at any segment
- Windows ADS (colon in path)
- Absolute paths or drive letters
- Control characters (ASCII < 32 or 127)
- Unsupported wildcards (`*`, `?`, `[`, `]`) outside a trailing `/**`
- Case-only mismatches (GitHub paths are case-sensitive)

**Rationale**: Case-insensitive matching would allow a path like `SRC/` to
bypass a restriction on `src/`. Ordinal (case-sensitive) matching matches
GitHub's actual filesystem semantics and prevents path-escape through case
variation.

**Consequences**:
- Positive: Path containment is deterministic and platform-independent.
- Positive: Case-only mismatches are explicitly rejected with a clear error.
- Negative: Requires callers to use the exact casing of the repository paths.
  This is enforced by the dispatch creation and preflight processes.

### D6: Singleton and Consumption Detection

**Decision**: The gate enumerates ALL repository PRs (open, closed, and
merged) via `gh api repos/:owner/:repo/pulls?state=all` with pagination. For
each PR other than the current PR, it conservatively scans every
code-fence-aware structured `**Dispatch ID**` field and compares every listed
value to the expected dispatch ID. The current PR is held to the stricter
exactly-one-heading/exactly-one-field rule in D3.

- If another **open** PR references the same Dispatch ID → `GATE_DUPLICATE_PR`
  (singleton violation).
- If a **closed or merged** PR references the same Dispatch ID →
  `GATE_DUPLICATE_PR` (dispatch already consumed).
- Only the current PR may reference this Dispatch ID while the envelope is
  active.

**Labels and assignees are not locks**: The gate does not check labels or
assignees for lock semantics. Only the dispatch file state and the PR
enumeration are authoritative.

**Stage-A limitation**: PR bodies remain editable, so historical PR scanning is
defense in depth rather than an immutable consumption ledger. The durable
control is the dispatch state transition: a dispatch must be expired when its
PR closes or merges and can never be reactivated or reused. Phase 7 must bind
that transition to an authenticated durable store before the gate becomes a
required Stage-B check.

**Consequences**:
- Positive: No ambiguity about which PR owns a dispatch.
- Positive: Duplicate active use is detected immediately; durable at-most-once
  use is enforced by the dispatch state transition.
- Negative: Enumerating all PRs requires pagination. If any page fails, the
  gate fails closed.

### D7: Evidence Semantics

**Decision**: The PR body must contain exactly one `## Evidence` heading with
substantive content. HTML comments (`<!-- ... -->`) and whitespace-only lines
are stripped before checking for content. A section containing only a simple
placeholder (for example `TBD`, `TODO`, `pending`, `none`, or `N/A`) is also
rejected. Human review still determines whether non-placeholder evidence is
credible and sufficient.

**Consequences**:
- Positive: Mechanical verification that the author considered evidence.
- Positive: Human reviewer can still judge evidence quality.
- Negative: An author could include arbitrary non-placeholder text and pass the
  mechanical check. Evidence quality remains a review concern.

### D8: Structured Error Codes

**Decision**: Every gate check failure produces a unique GATE_* error code.
The gate outputs a single JSON line to stdout:

```json
{"passed": false, "failed_check": "GATE_*", "message": "Human-readable description"}
```

Exit code 0 = all checks pass. Non-zero = first check failure.

| Code | Meaning |
|---|---|
| `GATE_INVALID_TARGET` | PR not targeting `master` or PR not open |
| `GATE_MISSING_ISSUE_REF` | Missing/duplicate/invalid Refs #N or envelope Issue mismatch |
| `GATE_DISPATCH_REF_MALFORMED` | Caller or PR body supplied a non-canonical, duplicate, or mismatched Dispatch ID |
| `GATE_ISSUE_NOT_OPEN` | Referenced Issue is closed or not found |
| `GATE_DISPATCH_NOT_FOUND` | Dispatch file does not exist |
| `GATE_DISPATCH_CORRUPT` | Dispatch file cannot be read safely or validator reports corruption/recovery failure |
| `GATE_DISPATCH_VALIDATION_FAILED` | Dispatch validator failed without a more specific mapped condition |
| `GATE_DISPATCH_INACTIVE` | Dispatch exists but is expired or superseded |
| `GATE_AC_MALFORMED` | Issue Canonical Acceptance Statement is malformed |
| `GATE_AC_HASH_MISMATCH` | Dispatch AC hash does not match current Issue AC text |
| `GATE_PATH_ESCAPE` | Changed file outside allowed paths, or empty files list |
| `GATE_BASE_NOT_AUTHORITATIVE` | Dispatch base SHA does not equal authoritative master |
| `GATE_BASE_STALE` | PR base SHA does not match envelope base, or PR head not descended |
| `GATE_DUPLICATE_PR` | Another open PR for same dispatch, or dispatch already consumed |
| `GATE_GOV_VERSION_MISMATCH` | Dispatch governance version does not match current version |
| `GATE_MISSING_EVIDENCE` | PR body missing Evidence section with substantive content |
| `GATE_TRANSPORT_FAILURE` | gh api call failed (network, auth, TLS) |
| `GATE_JSON_PARSE_FAILED` | GitHub API response is not valid JSON |
| `GATE_PAGINATION_AMBIGUOUS` | Paginated collection exceeded the 10,000-item safety cap |

**Consequences**:
- Positive: Every failure is identifiable by code for automation and alerting.
- Positive: CI can map error codes to actionable messages.
- Negative: No "pass with warnings" — the gate is binary pass/fail.

### D9: Link-Aware Pagination with a Safety Cap

**Decision**: List endpoints (PR files, all PRs) use `gh api --paginate --jq
'.[]'`. GitHub CLI follows the API `Link` headers, emits every page's elements
as individual JSON lines, and the gate accumulates them. A collection with
exactly 100 items is valid because page completion is determined by Link-aware
pagination rather than item count.

- More than 10,000 accumulated items fails closed with
  `GATE_PAGINATION_AMBIGUOUS` as a resource-exhaustion safety bound.
- Transport or JSON parsing failure on any page fails closed using the
  corresponding structured error.

**Consequences**:
- Positive: Exact page-boundary counts do not produce false failures.
- Positive: PRs with large file lists or repositories with many PRs are fully
  enumerated before policy evaluation.
- Negative: Collections above the 10,000-item safety cap require an explicit
  design revision rather than silently consuming unbounded resources.

### D10: Failure Recovery

**Decision**: On gate failure:
1. The PR author addresses the reported issue and pushes a new commit.
2. The gate re-validates from scratch — it is stateless.
3. If `master` advanced, the dispatch must be expired and a new one created.
   A re-run of the gate on the same PR with a stale base will fail at the
   base freshness check.
4. If the dispatch was consumed (merged PR), a new dispatch must be created
   for any follow-up work.

No auto-retry, no cache, no bypass. The gate is stateless and re-runs from
clean state on every invocation.

**Consequences**:
- Positive: No stale state between runs.
- Positive: Base advancement is always detected.
- Negative: A flaky network failure requires a full re-run.

### D11: Stage-A Status and Future CI Binding

**Decision**: In Stage-A the gate script exists and can be run manually or
in CI, but it is NOT yet a required CI check. The CI pipeline may be red
for unrelated reasons (pre-existing issues documented in Phase 7), and the
gate must not be the sole blocker preventing development.

Phase 7 will:
1. Fix baseline CI (frontend, backend-lint, backend-unit).
2. Add the gate check as a step in the CI workflow.
3. Before Stage-B activation, the gate becomes a required status check in the
   Ruleset.

Until Phase 7, the gate provides informational/validation value but does not
block merge. The ADR explicitly acknowledges that current legacy CI is red
and the gate alone does not compensate for that.

**Consequences**:
- Positive: The gate is deployed and testable before it becomes a blocker.
- Positive: Phase 7 has a concrete integration point.
- Negative: Until Stage-B, teams could merge without gate validation. The SOP
  and preflight provide complementary protection.

### D12: Governed Rollback

**Decision**: If a PR that passed the gate needs reversal after merge, the
rollback follows the standard governed procedure:

1. Create a new governance Issue and fresh dispatch from authoritative `master`.
2. Create a rollback branch from authoritative `master`.
3. Run `git revert <squash-merge-sha>` without `-m` (squash commits have one
   parent).
4. Verify the inverse diff and run applicable checks (preflight, gate).
5. Open a Draft PR and return through the normal review/merge path.

The gate does not need a special "rollback mode" — a revert PR must pass the
same checks as any other PR.

**Consequences**:
- Positive: Rollback is a governed PR like any other.
- Positive: No special gate bypass for reverts.
- Negative: Quick reverts are not possible outside the full pipeline.

### D13: No Current CI Check Requirement

**Decision**: The gate does not require legacy CI checks to be green. In
Stage A, the CI pipeline is intentionally known to be red (pre-existing CI
failures documented in Phase 7 scope). The gate validates dispatch integrity,
paths, singleton/consumption, and evidence — not CI status.

Phase 7 will bind the gate check into CI as a required status check, at which
point the gate result becomes a merge prerequisite. The gate itself does not
call gh to check CI status because CI status is inherently mutable and the
design avoids coupling the gate to ephemeral workflow-run state.

**Consequences**:
- Positive: The gate is independent of CI pipeline health.
- Positive: No coupling between gate logic and CI workflow-run state.
- Negative: CI status is not double-checked by the gate; it relies on
  GitHub's own required-status-check enforcement.

## Alternatives Considered

### Single Monolithic Script vs Child-Process Dispatch Validation

**Decision**: Child-process dispatch validation. Monolithic scripts would
duplicate dispatch validation logic and diverge. The child-process boundary
is cheap (a single `powershell.exe` invocation) and provides clean separation
of concerns.

### Using Local Git for Ancestry Check

**Decision**: Use the GitHub compare API (`repos/:owner/:repo/compare/<base>...<head>`)
instead of local `git merge-base`. The local checkout in CI may be a shallow
clone, making ancestry checks unreliable or requiring full unshallow. The
compare API always has the full history.

### Caller-Supplied Authority Override

**Decision**: Rejected. A parameter like `-OverrideBaseSha` or
`-SkipTransportCheck` would let callers bypass authoritative verification.
The gate has no such parameters — every call goes through `gh api`.

## Consequences

### Positive

1. **Deterministic checks**: Every gate invocation produces the same result
   for the same state — no flakiness from timing, caching, or local state.
2. **Fail-closed design**: Malformed input, transport failure, parse failure,
   and pagination safety-cap overflow all fail closed.
3. **Clean separation**: Dispatch validation and PR-specific checks are in
   separate scripts with a clear boundary.
4. **Testable isolation**: Fake `gh` and fake dispatch.ps1 enable full offline
   testing of the gate.
5. **Structured output**: JSON output is machine-parseable.
6. **Future-proof**: Stage-A deployment does not block merge; Phase 7
   integrates the gate into CI.

### Negative

1. **Network dependency**: Every gate invocation requires `gh api` access.
2. **No offline mode**: The gate cannot run without GitHub access.
3. **Pagination safety cap**: Collections above 10,000 items fail closed until
   the design is explicitly revised.
4. **No partial pass**: The gate is binary pass/fail with no warning mode.

### Mitigations

| Risk | Mitigation |
|---|---|
| Network failure | Fail closed with GATE_TRANSPORT_FAILURE; retry in CI |
| Large collections | Link-aware pagination; fail closed above 10,000 items |
| Dispatch script not found | Clear GATE_DISPATCH_NOT_FOUND error |
| gh version compatibility | Uses documented `--paginate --jq` flags available in gh 2.x |
| CI pipeline red | Stage-A does not require green CI; Phase 7 fixes CI |

## Related Documents

| Document | Path | Relationship |
|---|---|---|
| Delivery SOP | [../engineering/delivery-sop.md](../engineering/delivery-sop.md) | Canonical workflow; gate is step 7 |
| ADR-001 | [./ADR-001-multi-client-delivery-governance.md](./ADR-001-multi-client-delivery-governance.md) | Parent ADR establishing gate concept |
| ADR-002 | [./ADR-002-dispatch-protocol.md](./ADR-002-dispatch-protocol.md) | Dispatch protocol that gate depends on |
| Gate Contract | [../../specs/064-delivery-governance/contracts/governance-state-gate.md](../../specs/064-delivery-governance/contracts/governance-state-gate.md) | Gate check list and fail-closed semantics |
| Dispatch Envelope Contract | [../../specs/064-delivery-governance/contracts/dispatch-envelope.md](../../specs/064-delivery-governance/contracts/dispatch-envelope.md) | Envelope fields and validation rules |
| Handoff Invariants Contract | [../../specs/064-delivery-governance/contracts/handoff-invariants.md](../../specs/064-delivery-governance/contracts/handoff-invariants.md) | Handoff protocol invariants |
| Preflight Gate | [../../scripts/governance/preflight.ps1](../../scripts/governance/preflight.ps1) | Pre-commit gate (Phase 3, active) |
| Dispatch Script | [../../scripts/governance/dispatch.ps1](../../scripts/governance/dispatch.ps1) | Dispatch state machine (Phase 6b, accepted) |
| Gate Script | [../../scripts/governance/gate.ps1](../../scripts/governance/gate.ps1) | This implementation |

# Trusted governance gate runner — 2026-07-16

## Scope

Issue #100 / Dispatch `req-100-trusted-gate-20260716-03` adds the smallest
trusted runner slice. It changes only the workflow, the trusted wrapper, its
self-contained tests, this evidence, ADR-003, the delivery SOP, and the one
dispatch envelope. No product code, migrations, worker code, CI quality gates,
or Stage-B ruleset settings are in scope.

## Trust boundary

1. `pull_request_target` receives only read permissions (`contents`,
   `pull-requests`, `issues`).
2. The workflow resolves `master` through the authenticated API, checks out
   that exact 40-character SHA with `persist-credentials: false`, and verifies
   `git rev-parse HEAD` before invoking the wrapper.
3. The wrapper reads PR metadata and requires exactly one `Refs #N` line and
   one canonical Dispatch ID (including the SOP's bullet/backtick form).
4. It reads exactly `.github/dispatches/<id>.json` from the immutable PR head
   SHA via the authenticated Contents API. The response is bounded to 64 KiB,
   must be a base64 file, and its Git blob SHA, path, size, UTF-8 JSON schema,
   active state, and Issue binding are checked.
5. Only that one decoded JSON file is staged beside trusted copies of
   `gate.ps1` and `dispatch.ps1` in a temporary directory. The PR head is
   never checked out and no PR-controlled script is executed.
6. A second PR read detects a changed head SHA or fork repository. Failures
   emit stable error codes and bounded, sanitized artifacts.

## Verification

PowerShell parser checks passed for the wrapper, workflow-adjacent test, and
all existing governance scripts. The new boundary suite passed:

```
trusted-gate.Tests.ps1: 11 passed, 0 failed
```

The repository's existing self-contained governance harness remains green:

```
dispatch.Tests.ps1: 35 passed, 0 failed
gate.Tests.ps1: 47 passed, 0 failed
preflight.Tests.ps1: 13 passed, 0 failed
total: 95 passed, 0 failed
```

The boundary tests cover malformed/duplicate Dispatch fields, wrong target,
deleted fork/head metadata, Contents API path/type mismatch, size overflow,
transport failure, and canonical bullet/backtick parsing. `gate.Tests.ps1`
continues to cover duplicate active dispatches, stale bases, path escape,
Issue/AC mismatch, malformed JSON, pagination, and evidence failures.

## Stage-A limitation and activation

This workflow is informational in Stage-A. A successful local or PR run does
not authorize Stage-B ruleset activation. Because a `pull_request_target`
workflow is loaded from the base branch, a positive live run can be recorded
only after this workflow lands on `master` and a fresh follow-up PR exercises
it; this branch therefore claims no live GitHub pass. Stage-B still requires
the documented positive/negative drills, baseline product P0 closure, and an
explicit owner decision to make `governance-gate` required.

## Rollback

Use a fresh governed revert Issue/Dispatch/PR. Do not delete or edit the
dispatch in place, and do not merge this slice without the existing owner
PR-only review/bypass path.

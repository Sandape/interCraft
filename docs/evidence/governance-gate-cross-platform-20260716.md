# Governance Gate cross-platform evidence

Issue: #98  
Dispatch: `req-098-governance-gate-20260716-02`  
Base: `91e6065d3c0ab5660db655898ec768b7c4af5edd`

## Change

`scripts/governance/gate.ps1` no longer assumes
`$PSHOME\powershell.exe`. It resolves a child host from the executable PATH,
preferring `pwsh` (GitHub Actions/Linux) and falling back to
`powershell.exe` (Windows PowerShell). If neither is present, it returns the
existing fail-closed `GATE_DISPATCH_VALIDATION_FAILED` result.

## Verification

- Standalone `dispatch.Tests.ps1`: 35 passed, 0 failed.
- Standalone `gate.Tests.ps1`: 47 passed, 0 failed.
- Standalone `preflight.Tests.ps1`: 13 passed, 0 failed.
- Current Windows host selected `powershell.exe` through `Get-Command`; the
  Linux `pwsh` branch is exercised by the same resolver when the runner offers
  `pwsh` and must be confirmed by the PR Actions job.
- Real GitHub API Gate probe for PR #99 with Dispatch
  `req-098-governance-gate-20260716-02`: `{"passed":true}`.
- No product paths, production secrets, or Stage-B Ruleset settings changed.

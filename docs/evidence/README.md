# Evidence Guide

Evidence files record what was observed during testing or manual verification.
They are not requirement sources.

## Layout

| Path | Purpose |
|---|---|
| `docs/evidence/PHASE*_*/` | Phase verification runs and logs. |
| `docs/evidence/BUG/` | Bug reproduction evidence. |
| `docs/e2e/` | Feature-specific E2E screenshots and notes from earlier runs. |
| `docs/evidence/unclassified/2026-06-root-artifacts/` | Root screenshots and snapshots archived during documentation cleanup. |

## Naming

Use stable names that identify the feature, date, and observation:

```text
docs/evidence/<feature-or-run>/<step-number>-<short-description>.png
docs/evidence/<feature-or-run>/<command-or-check>.log
docs/evidence/<feature-or-run>/SCORECARD.md
```

## Rules

- Do not place new screenshots or Playwright snapshots in the repository root.
- Link evidence from `specs/*/requirements-status.md` when using it to mark a
  requirement `done`.
- Keep raw logs when they are needed to debug failures; summarize key outcomes in
  a `SCORECARD.md` or feature status file.
- Do not delete old evidence during cleanup unless a separate deprecation task
  verifies it is duplicated and no longer referenced.


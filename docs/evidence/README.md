# Evidence Guide

Evidence files record what was observed during testing or manual verification.
They are not requirement sources.

## Layout

| Path | Purpose |
|---|---|
| `docs/evidence/<feature-or-run>/` | New screenshots, traces, logs, and scorecards for verification runs. |
| Feature-specific evidence folders | Evidence kept beside a feature when the feature spec explicitly owns it. |

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
- Keep raw logs only when they are needed to debug failures; summarize key
  outcomes in a `SCORECARD.md` or feature status file.
- Old unreferenced evidence was removed during the documentation slimming pass.

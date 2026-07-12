@AGENTS.md
@docs/engineering/delivery-sop.md

# InterCraft Claude Context

Claude-specific notes — the routing layer and delivery SOP are imported above.

## Claude Notes

- Use `specs/` as the requirements source of truth.
- Historical requirement documents were removed after being folded into the
  canonical specs. Use git history only for old context.
- Add Playwright E2E specs under `tests/e2e/`.
- Do not move source directories during documentation cleanup.
- Keep generated screenshots, logs, and manual verification artifacts out of
  the repository root; use `docs/evidence/`.
- Use `/memory` or `/context` only to verify loaded rules — they cannot bypass
  repository-level delivery constraints.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/063-derive-page-fill/plan.md
<!-- SPECKIT END -->

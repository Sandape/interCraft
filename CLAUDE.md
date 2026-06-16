# InterCraft Claude Context

Claude-specific context should stay thin. The project-wide source of truth for
agent routing is [AGENTS.md](./AGENTS.md).

## Required First Reads

1. [AGENTS.md](./AGENTS.md)
2. [specs/README.md](./specs/README.md)
3. `.specify/feature.json`
4. The active feature `README.md`
5. [docs/testing/README.md](./docs/testing/README.md)
6. [docs/architecture/source-map.md](./docs/architecture/source-map.md)

## Claude Notes

- Use `specs/` as the requirements source of truth.
- Treat `docs/modules/*` and old roadmap documents as legacy context.
- Add new Playwright E2E specs under `tests/e2e/`, not root `e2e/`.
- Do not move source directories during documentation cleanup.
- Keep generated screenshots, logs, and manual verification artifacts out of the
  repository root; use `docs/evidence/`.


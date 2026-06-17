# InterCraft Documentation

This is the documentation entry point for humans and AI agents.

## Start Here

| Need | Canonical Entry |
|---|---|
| Current requirements | [specs/README.md](../specs/README.md) |
| Current active feature | `.specify/feature.json`, then the feature README in `specs/` |
| Test strategy and commands | [testing/README.md](./testing/README.md) |
| Evidence guidance | [evidence/README.md](./evidence/README.md) |
| Source tree map | [architecture/source-map.md](./architecture/source-map.md) |
| Documentation decision | [decisions/ADR-001-documentation-structure.md](./decisions/ADR-001-documentation-structure.md) |

## Documentation Layers

| Layer | Path | Authority |
|---|---|---|
| Requirements source of truth | `specs/` | Canonical for implementation. |
| API/UI contracts | `specs/*/contracts/` | Canonical for feature interfaces. |
| Task plans | `specs/*/tasks.md` | Canonical for feature execution order. |
| Test guidance | `docs/testing/` | Canonical for test commands and test directory ownership. |
| Evidence guidance | `docs/evidence/` | Storage policy for new verification artifacts. |
| Architecture decisions | `docs/decisions/` | Decision history and documentation policy. |

Historical requirement documents and unreferenced evidence were removed after
their useful context was folded into the canonical specs. Use git history only
when old context is specifically needed.

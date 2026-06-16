# InterCraft Documentation

This is the documentation entry point for humans and AI agents.

## Start Here

| Need | Canonical Entry |
|---|---|
| Current requirements | [specs/README.md](../specs/README.md) |
| Current active feature | `.specify/feature.json`, then the feature README in `specs/` |
| Test strategy and commands | [testing/README.md](./testing/README.md) |
| Evidence and screenshots | [evidence/README.md](./evidence/README.md) |
| Source tree map | [architecture/source-map.md](./architecture/source-map.md) |
| Documentation structure decision | [decisions/ADR-001-documentation-structure.md](./decisions/ADR-001-documentation-structure.md) |

## Documentation Layers

| Layer | Path | Authority |
|---|---|---|
| Requirements source of truth | `specs/` | Canonical for implementation. |
| API/UI contracts | `specs/*/contracts/` | Canonical for feature interfaces. |
| Task plans | `specs/*/tasks.md` | Canonical for feature execution order. |
| Test guidance | `docs/testing/` | Canonical for test commands and test directory ownership. |
| Evidence | `docs/evidence/`, `docs/e2e/` | Verification records, not requirements. |
| Historical requirements | `docs/modules/`, `docs/PERSISTENCE_REQUIREMENTS.md`, `docs/DEVELOPMENT_ROADMAP.md` | Legacy context only. |

## Historical Documents

The following documents remain useful for background, but do not override
feature specs:

- [PERSISTENCE_REQUIREMENTS.md](./PERSISTENCE_REQUIREMENTS.md)
- [DEVELOPMENT_ROADMAP.md](./DEVELOPMENT_ROADMAP.md)
- [ANALYSIS_REPORT.md](./ANALYSIS_REPORT.md)
- [modules/](./modules/)

See [requirements/legacy-map.md](./requirements/legacy-map.md) for how legacy
documents map to canonical specs.


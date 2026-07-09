# REQ-049 Markdown Editor Cutover and Pagination

This feature retires the legacy structured resume editor and makes the
REQ-047 Markdown editor the only resume editing route.

## Canonical Artifacts

- Specification: [spec.md](./spec.md)
- Implementation plan: [plan.md](./plan.md)
- Research: [research.md](./research.md)
- Data model: [data-model.md](./data-model.md)
- Contracts: [contracts/](./contracts/)
- Quickstart: [quickstart.md](./quickstart.md)
- Requirement status: [requirements-status.md](./requirements-status.md)

## Scope

- Markdown-only resume editing entry points.
- Safe conversion or fallback for older structured resume content.
- Polished `::: left` and `::: right` contact rendering.
- Real multi-page Markdown preview and PDF export parity.
- Smart one-page fallback when one-page fitting is infeasible.


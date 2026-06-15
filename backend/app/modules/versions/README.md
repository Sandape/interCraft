# M07 — Resume Versioning

**Purpose**: Manual save full snapshots; rollback creates a new branch.

**Public API** (see `specs/001-intercraft-product-spec/contracts/versions.md`):
- `GET    /api/v1/resume-branches/{id}/versions`
- `POST   /api/v1/resume-branches/{id}/versions` — manual save (full snapshot)
- `GET    /api/v1/resume-branches/{id}/versions/{n}` — auto-restore snapshot
- `POST   /api/v1/resume-branches/{id}/versions/{n}/rollback` — create new branch

**CLI**:
```bash
uv run python -m app.modules.versions.cli list     --branch-id <UUID> --user-id <UUID> --json
uv run python -m app.modules.versions.cli save     --branch-id <UUID> --user-id <UUID> --label "v1"
uv run python -m app.modules.versions.cli get      --branch-id <UUID> --version-no 1 --user-id <UUID>
uv run python -m app.modules.versions.cli rollback --branch-id <UUID> --version-no 1 --user-id <UUID>
```

**Notes**:
- Phase 1 always writes `is_full_snapshot=true` from the manual-save path.
- The `diff_patch` path is reserved for the ARQ auto-snapshot task; the task body
  is a placeholder for now (`auto_snapshot.py`).
- Restoration walks the diff chain recursively, capped at `MAX_RESTORE_DEPTH = 100`.
- `jsonpatch` (PyPI) provides `apply_patch` for restoration; the same algorithm is
  exercised in `tests/integration/test_jsonpatch_parity.py` against a Node fixture
  using `fast-json-patch`.

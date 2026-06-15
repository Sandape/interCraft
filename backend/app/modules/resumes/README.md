# M06 — Resume Branch / Block

**Purpose**: Notion-style resume tree (branches + blocks), drag-reorder via fractional indexing, COW on derived branches.

**Public API** (see `specs/001-intercraft-product-spec/contracts/resumes.md` and `blocks.md`):

Branches:
- `GET /api/v1/resume-branches` — list
- `POST /api/v1/resume-branches` — create (optional `parent_id` → clone parent blocks)
- `GET /api/v1/resume-branches/{id}`
- `PATCH /api/v1/resume-branches/{id}`
- `DELETE /api/v1/resume-branches/{id}` (cannot delete main)
- `POST /api/v1/resume-branches/{id}/refresh-from-parent`

Blocks:
- `GET /api/v1/resume-branches/{id}/blocks`
- `POST /api/v1/resume-branches/{id}/blocks`
- `GET /api/v1/resume-blocks/{id}`
- `PATCH /api/v1/resume-blocks/{id}`
- `PATCH /api/v1/resume-blocks/{id}/reorder`
- `DELETE /api/v1/resume-blocks/{id}`

**CLI**:
```bash
uv run python -m app.modules.resumes.cli list   --user-id <UUID> --json
uv run python -m app.modules.resumes.cli create --user-id <UUID> --name "字节前端" --main
uv run python -m app.modules.resumes.cli reorder --block-id <UUID> --prev-id <UUID> --next-id <UUID> --user-id <UUID>
```

**Notes**:
- `order_index` uses `python-fractional-indexing` (same algorithm as frontend `fractional-indexing`).
- Phase 1 simplifies COW to "clone all parent blocks on create" (max 100 blocks per branch, < 10 KB).
- Soft-delete cascades from branches to blocks to versions.
- RLS is enabled on `resume_branches`, `resume_blocks`, and `resume_versions`.

# REQ-095 capability registry fixture evidence

## Scope

This change addresses Issue #95 only. The clean `master` checkout was missing
`backend/tests/fixtures/ai_capability_registry.json`, which caused
`ResumeDeriveAdapter` construction to fail before a derive run could be queued.
No migration, RLS, worker, or product-runtime files are included.

## Reproduction and verification

- RED: `uv run pytest -q tests/unit/test_061_capability_registry_fixture.py`
  failed with `FileNotFoundError` for the missing fixture.
- GREEN: the same command passed: `1 passed, 2 warnings`.
- Compatibility check: `uv run pytest -q tests/eval/test_061_eval_dataset_coverage.py`
  passed: `8 passed, 2 warnings`.
- `git diff --check` passed.

The fixture bytes were compared with the preserved dirty-root asset before
staging; they are identical. It contains registry metadata only and no
credentials.

## Dispatch

- Dispatch: `req-095-capability-registry-20260716-01`
- Issue: #95
- Allowed paths: dispatch metadata, the fixture, `backend/tests/unit/**`, and
  `docs/evidence/**`.
- Review/merge remains a human owner action; this branch is not merged by this
  evidence record.

---
name: req-044-cross-saved-views
description: REQ-044 CROSS 2026-07-04 — Saved Views 真实化 + 12-action audit taxonomy + role-aware 5 角色 matrix;US1 stub → Phase 2 落地的铁律 A 第 3 次实证
metadata:
  type: project
---

REQ-044-CROSS shipped 2026-07-04 (commit 2e7c667).

Scope:
- backend/app/modules/admin_console/saved_views/ new subpackage
  (schemas / repository / service / api) — 5 endpoints (list / create
  / get / patch / delete) + 1 health mounted at
  /api/v1/admin-console/saved-views
- 12th audit action `saved_view_change` (target_kind='saved_view')
  added to audit.VALID_ACTIONS + governance AUDIT_ACTIONS — widens
  the audit taxonomy from 11 to 12 tokens
- 2 new capability tokens: SAVED_VIEW_VIEW (granted to 6 roles except
  viewer) + SAVED_VIEW_CHANGE (granted to 5 editor roles; reviewer
  remains read-only)
- frontend savedViewRepository.ts 5 methods real impl (removed
  throw NotImplementedError) + new SavedViewsPanel real render +
  RoleBadgeDropdown clickable + SaveCurrentViewButton captures filter
- frontend SharedWithRole union mirrors backend Literal (5 roles)
- 19 pytest contract tests + 16 vitest tests pass
- 0 new typecheck errors (baseline 36 resume v2 errors unchanged)

Why: US1 (IA shell) stubbed the savedViewRepository with explicit
NotImplementedError throws per 铁律 A (memory req_032_v2_repo_stub_trap).
The CROSS US was the planned Phase 2 landing. Real persistence is
critical because every saved_view change MUST emit a 12th audit
event (FR-034 AC-6.7 + SC-009) — without the repo, audit can't fire.

How to apply:
- Any new "saved_view" features (Phase 3+) build on this baseline.
- Real DB migration lands in Phase 2 batch 5 (widens admin_audit_log
  CHECK constraint to accept `saved_view_change` action + new
  target_kind `saved_view`).
- Cross-team contract: SharedWithRole union widening MUST sync
  frontend types/admin-console.ts ↔ backend
  app/modules/admin_console/saved_views/schemas.py SharedWithRole
  Literal (memory feedback_cross_team_contract_l031).
- Frontend legacy 'trusted' / 'provisional' / 'unverified' trustStatus
  values are mapped to strict 'verified' / 'pending' / 'deprecated'
  at the repository layer — keep this compat until all callers migrate.

Related: [[req_032_v2_repo_stub_trap]], [[feedback_cross_team_contract_l031]],
[[req_044_us7_metric_trust]], [[req_044_us5_cross_agent_retry]]
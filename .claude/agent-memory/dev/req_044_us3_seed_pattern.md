---
name: req-044-us3-seed-pattern
description: REQ-044 US3 9-endpoint AI Operations workspace — 4 seed helpers + 9 endpoint surface + capability role map expansion pattern
metadata:
  type: project
---

# REQ-044 US3 — AI Operations seed + capability expansion pattern (2026-07-04)

The REQ-044 US3 ship pattern crystallizes 4 seed helpers behind 9 endpoints
plus 10th health, all under `backend/app/modules/admin_console/ai_operations/`.

## Why: front-end renders 11 surfaces (4 KPI tiles + 5 charts + 1 cost card
+ 1 eval/badcase summary + 1 quality issues panel), each needs an endpoint,
but the seed (no real AIInvocationRecord data yet) must drive consistent
numbers across the suite.

## How to apply:
- Start from seed helpers (not endpoints): define `seed_demo_*()` first,
  return lists/dicts with internally consistent cost = prompt/1000*rate +
  completion/1000*rate. Service layer `get_*()` calls these seeds.
- Capability token name: `AI_OPERATIONS_VIEW`. Required role grants: pm,
  owner, admin, operations, maintainer. viewer is denied (FR-031).
- ALWAYS update `_ROLE_GRANTS` for ALL roles when adding capability
  (do not assume token declaration = grant). Same trap as US1 + US2.
- EC-3 cost-stale default: `last_reconciled_at = now - 7d`, `stale` flags
  when > 14d threshold. Tunable `COST_RECONCILIATION_STALE_DAYS = 14`.
- Cost-quality tradeoff thresholds: cost up ≥ 10% + quality down ≥ 5%
  → `flagged = True`, `severity = critical` (FR-019 hard constraint).
- FR-032 privacy guard: AIQualityIssue schema MUST NOT carry
  raw_prompt / raw_model_output / raw_resume / raw_interview_answer.
  Contract test asserts this intersection is empty.

## Files shipped (31 total):
- Backend 4 files (schemas/service/api/__init__) + 1 contract test
- Backend 3 edits (__init__.py + auth.py + main.py)
- Frontend 1 types + 1 api + 1 hooks + 10 components + 1 page + 1 css + 1 test
- 2 page edits (AIOperations.tsx upgrade + main.tsx CSS import)
- E2E + AC matrix + evidence log

## Test counts:
- pytest 22/22 pass (US3) + 35 regression (US1/US2) = 57 total
- vitest 21/21 pass (US3 components) + 35 regression (admin suite)
- typecheck 0 US3 errors; 36 pre-existing resume/v2 errors (out of scope)
- Playwright 11/11 INFRA-BLOCKED (backend unreachable in CI; documented)

Related: [[feedback_ac_lock_pattern]] (US3 locked in cycle 1 with
FR-019 cost-quality thresholds accepted, FR-032 strict-no-sensitive-payloads
guarded by contract test).

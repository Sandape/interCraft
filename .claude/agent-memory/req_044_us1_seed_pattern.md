---
name: req-044-us1-seed-pattern
description: REQ-044 US1 decision_signals seed-only Phase 1 pattern — 8 sample signals covering all 6 categories × 4 confidence tiers; static seed validates FR-007~FR-010 visual/contract without real metric_panel wiring
metadata:
  type: project
---

REQ-044 US1 (Command Center decision queue, FR-007~FR-010) ships with a static seed of 8 decision signals covering all 6 FR-007 categories × all 4 FR-009 confidence tiers, plus at least 1 stale + 1 partial_baseline + 1 candidate signal.

**Why:** Real metric_panel → signal aggregate pipeline is out of scope for this PR (Phase 2 batch 2 work for other team). Silent empty list fallback would violate Iron Rule A (stub must throw NotImplementedError). Seed-only pattern lets contract tests validate FR-008/SC-002 statically without real DB.

**How to apply:** When implementing PM-facing surfaces that depend on async metric aggregation:
1. Write `seed_demo_signals()` pure function returning curated list (cover all enum variants)
2. Mount new router under new prefix (`/api/v1/admin-console/command-center`) — don't pollute existing `admin_console/api.py`
3. Backend contract tests call service directly (no DB); frontend Playwright specs split: 1 happy path (DB-dependent, INFRA-BLOCKED acceptable) + 5+ static guards (grep file content for field literals)
4. Mark real-data wiring as `[CROSS-TEAM-DEBT] Phase 2 batch N` in service docstring + AC matrix
5. Pydantic `extra="forbid"` + seed field completeness must be declared together (otherwise 8/13 tests fail on first run)

**Lesson source:** commit pending (REQ-044-US1) — see [[lessons-learned]] entry "260704 REQ-044-US1 decision_signals seed-only Phase 1 pattern"

Related: [[gap-b-get-envelope]], [[req-032-v2-repo-stub-trap]]